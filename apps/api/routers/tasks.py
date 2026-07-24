"""Tasks router - POST /tasks endpoint.

Creates a workspace directory for each run and persists file changes.
"""

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, verify_api_key
from core.agents.coder import CoderAgent
from core.orchestrator.state import create_initial_state
from core.router.model_router import ModelRouter
from core.router.registry import seed_model_profiles
from core.schemas import RunResponse, TaskCreate
from db.models import FileChange, Run

router = APIRouter()

# Base directory for run workspaces
WORKSPACES_DIR = Path(tempfile.gettempdir()) / "ai-team-workspaces"


@router.post(
    "/tasks",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and execute a development task",
)
async def create_task(
    task: TaskCreate,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    """Create a new development task and execute it with the Coder Agent.

    Creates an isolated workspace directory for the run, executes the
    agent pipeline, and persists file changes to the database.

    Args:
        task: The task creation schema with description.
        api_key: Validated API key.
        db: Database session.

    Returns:
        RunResponse with the complete run information.

    Raises:
        HTTPException: If task creation or execution fails.
    """
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Create workspace directory for this run
    workspace_path = WORKSPACES_DIR / run_id
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Create run record
    run = Run(
        id=run_id,
        task_description=task.description,
        status="running",
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    await db.flush()

    # Ensure model profiles are seeded
    await seed_model_profiles(db)

    # Create ModelRouter and Coder Agent
    model_router = ModelRouter(db)
    agent = CoderAgent()
    state = create_initial_state(
        run_id=run_id,
        user_request=task.description,
        router=model_router,
    )
    state["workspace_path"] = str(workspace_path)

    try:
        result = await agent.run(state)

        # Update run with results
        run.status = result.get("status", "completed")
        run.generated_code = result.get("generated_code")
        run.tokens_used = result.get("tokens_used", 0)
        run.updated_at = datetime.now(timezone.utc)

        # Persist file changes to database
        files_changed = result.get("files_changed", [])
        for fc in files_changed:
            file_change = FileChange(
                run_id=run_id,
                file_path=fc.file_path,
                action=fc.action,
                content=fc.content[:10000] if fc.content else None,  # Limit content size
                diff=fc.diff[:10000] if fc.diff else None,
            )
            db.add(file_change)
        await db.flush()

        if result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Task execution failed: {result.get('error', 'Unknown error')}",
            )

        return RunResponse(
            id=run.id,
            task_description=run.task_description,
            status=run.status,
            generated_code=run.generated_code,
            tokens_used=run.tokens_used,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        run.status = "failed"
        run.updated_at = datetime.now(timezone.utc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
