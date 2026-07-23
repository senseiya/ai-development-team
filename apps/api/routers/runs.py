"""Runs router - GET /runs/{id} endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, verify_api_key
from core.schemas import RunResponse
from db.models import Run

router = APIRouter()


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
    summary="Get run details by ID",
)
async def get_run(
    run_id: str,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    """Get the details of a specific run by its ID.

    Args:
        run_id: The unique run identifier.
        api_key: Validated API key.
        db: Database session.

    Returns:
        RunResponse with the run information.

    Raises:
        HTTPException: If the run is not found.
    """
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with id '{run_id}' not found.",
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
