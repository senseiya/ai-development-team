"""Custom LangGraph checkpointer that persists to PostgreSQL.

Saves AgentState checkpoints to the run_checkpoints table,
enabling pause/resume, audit, and replay of any run.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import RunCheckpoint

logger = logging.getLogger(__name__)


class PostgresCheckpointer(BaseCheckpointSaver[str]):
    """Checkpointer that persists LangGraph checkpoints to PostgreSQL.

    Each checkpoint is stored as a row in run_checkpoints, linked
    to a run_id. This enables:
    - Pausing and resuming runs
    - Auditing the state at any point in the pipeline
    - Replaying from any checkpoint
    """

    def __init__(self, db_factory) -> None:
        """Initialize the checkpointer.

        Args:
            db_factory: Async callable that returns an AsyncSession.
                       Typically `async_session` from db.session.
        """
        super().__init__()
        self._db_factory = db_factory

    async def aget_tuple(
        self,
        config: dict[str, Any],
    ) -> CheckpointTuple | None:
        """Load a checkpoint by config.

        Args:
            config: Must contain {'configurable': {'run_id': str, 'thread_id': str}}.

        Returns:
            CheckpointTuple if found, None otherwise.
        """
        configurable = config.get("configurable", {})
        run_id = configurable.get("run_id")
        thread_id = configurable.get("thread_id", "default")

        if not run_id:
            return None

        async with self._db_factory() as session:
            result = await session.execute(
                select(RunCheckpoint)
                .where(RunCheckpoint.run_id == run_id)
                .where(RunCheckpoint.thread_id == thread_id)
                .order_by(RunCheckpoint.step.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()

            if row is None:
                return None

            checkpoint_data = json.loads(row.checkpoint_data)
            metadata_data = json.loads(row.metadata) if row.metadata else {}

            checkpoint = Checkpoint(
                v=checkpoint_data.get("v", 1),
                id=checkpoint_data.get("id", ""),
                ts=checkpoint_data.get("ts", ""),
                channel_values=checkpoint_data.get("channel_values", {}),
                channel_versions=checkpoint_data.get("channel_versions", {}),
                versions_seen=checkpoint_data.get("versions_seen", {}),
            )

            metadata = CheckpointMetadata(
                source=metadata_data.get("source", "update"),
                step=metadata_data.get("step", 0),
                writes=metadata_data.get("writes", {}),
            )

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
            )

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Save a checkpoint to the database.

        Args:
            config: Must contain {'configurable': {'run_id': str, 'thread_id': str}}.
            checkpoint: The checkpoint to save.
            metadata: Checkpoint metadata.
            new_versions: New channel versions.

        Returns:
            Updated config with checkpoint info.
        """
        configurable = config.get("configurable", {})
        run_id = configurable.get("run_id", "unknown")
        thread_id = configurable.get("thread_id", "default")

        checkpoint_data = {
            "v": checkpoint.v,
            "id": checkpoint.id,
            "ts": checkpoint.ts,
            "channel_values": checkpoint.channel_values,
            "channel_versions": checkpoint.channel_versions,
            "versions_seen": checkpoint.versions_seen,
        }

        metadata_data = {
            "source": metadata.source,
            "step": metadata.step,
            "writes": metadata.writes,
        }

        # Extract step number for ordering
        step = metadata.step if metadata.step is not None else 0

        async with self._db_factory() as session:
            run_checkpoint = RunCheckpoint(
                run_id=run_id,
                thread_id=thread_id,
                step=step,
                checkpoint_data=json.dumps(checkpoint_data),
                meta_data=json.dumps(metadata_data),
                created_at=datetime.now(timezone.utc),
            )
            session.add(run_checkpoint)
            await session.flush()

        logger.debug(
            "Checkpoint saved: run=%s thread=%s step=%d",
            run_id,
            thread_id,
            step,
        )

        return {
            **config,
            "configurable": {
                **configurable,
                "checkpoint_step": step,
            },
        }

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save pending writes. No-op for now; writes are captured in aput."""
        pass
