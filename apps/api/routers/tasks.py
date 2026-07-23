"""Tasks router - POST /tasks endpoint."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, verify_api_key
from core.agents.coder import CoderAgent
from core.schemas import RunResponse, TaskCreate
from db.models import Run

router = APIRouter()


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

    This endpoint:
    1. Creates a new run record in the database
    2. Executes the Coder Agent to generate code
    3. Updates the run with the generated code
    4. Returns the complete run information

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
    now = datetime.utcnow()

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

    # Execute Coder Agent
    agent = CoderAgent()
    state = {
        "run_id": run_id,
        "user_request": task.description,
        "status": "running",
        "tokens_used": 0,
    }

    try:
        result = await agent.run(state)

        # Update run with results
        run.status = result.get("status", "completed")
        run.generated_code = result.get("generated_code")
        run.tokens_used = result.get("tokens_used", 0)
        run.updated_at = datetime.utcnow()

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
        run.updated_at = datetime.utcnow()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
