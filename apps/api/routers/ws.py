"""WebSocket endpoint for real-time run progress via Redis pub-sub."""

from __future__ import annotations

import json
import logging

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Redis channel prefix for run progress updates
CHANNEL_PREFIX = "run:progress:"


class RunProgressPublisher:
    """Publishes run progress updates to Redis pub-sub.

    Used by the orchestrator/graph to broadcast state changes
    that WebSocket clients can subscribe to.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        """Initialize the publisher.

        Args:
            redis_client: Optional Redis client. If None, creates one.
        """
        self._redis = redis_client

    async def _get_client(self) -> redis.Redis:
        """Get or create the Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
        return self._redis

    async def publish(self, run_id: str, data: dict) -> None:
        """Publish a progress update for a run.

        Args:
            run_id: The run identifier.
            data: Dictionary of progress data to send.
        """
        client = await self._get_client()
        channel = f"{CHANNEL_PREFIX}{run_id}"
        message = json.dumps(data)
        await client.publish(channel, message)
        logger.debug("Published to %s: %s", channel, data.get("status", "update"))

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None


@router.websocket("/ws/runs/{run_id}")
async def run_progress_ws(
    websocket: WebSocket,
    run_id: str,
) -> None:
    """WebSocket endpoint for real-time run progress.

    Clients connect to /ws/runs/{run_id} and receive JSON messages
    whenever the run state changes. Messages are published via
    Redis pub-sub by the orchestrator.

    Message format:
    {
        "run_id": "abc-123",
        "status": "coding",
        "agent": "coder",
        "iteration": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "detail": "Code generated using qwen-2.5-coder-32b"
    }
    """
    await websocket.accept()
    logger.info("WebSocket connected for run %s", run_id)

    client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    pubsub = client.pubsub()
    channel = f"{CHANNEL_PREFIX}{run_id}"
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    await websocket.send_text(data)
                elif isinstance(data, bytes):
                    await websocket.send_text(data.decode())

            # Also send a ping every 30s to keep connection alive
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for run %s", run_id)
    except Exception as e:
        logger.error("WebSocket error for run %s: %s", run_id, e)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await client.close()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
