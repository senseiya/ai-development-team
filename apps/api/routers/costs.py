"""Cost dashboard endpoint — GET /costs/summary.

Provides aggregated token usage and cost breakdown across all runs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_current_user_id, get_db_session
from db.models import Run

router = APIRouter()


class CostBreakdownItem(BaseModel):
    """Single cost breakdown entry."""

    agent: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostSummaryResponse(BaseModel):
    """Aggregated cost summary across all runs."""

    total_runs: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_tokens_per_run: float = 0.0
    avg_cost_per_run: float = 0.0
    runs_by_status: dict[str, int] = {}
    top_models: list[dict] = []


class RunCostResponse(BaseModel):
    """Cost summary for a single run."""

    run_id: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    breakdown: list[CostBreakdownItem] = []


@router.get(
    "/costs/summary",
    response_model=CostSummaryResponse,
    summary="Get aggregated cost and token summary",
)
async def get_cost_summary(
    api_key: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> CostSummaryResponse:
    """Get aggregated cost and token usage across all runs.

    Returns total runs, total tokens, average per-run metrics,
    and runs grouped by status.
    """
    # Total runs and tokens
    result = await db.execute(
        select(
            func.count(Run.id),
            func.coalesce(func.sum(Run.tokens_used), 0),
        )
    )
    row = result.one()
    total_runs = row[0] or 0
    total_tokens = row[1] or 0

    # Runs by status
    status_result = await db.execute(select(Run.status, func.count(Run.id)).group_by(Run.status))
    runs_by_status = {row[0]: row[1] for row in status_result.all()}

    avg_tokens = total_tokens / total_runs if total_runs > 0 else 0.0

    return CostSummaryResponse(
        total_runs=total_runs,
        total_tokens=total_tokens,
        total_cost_usd=0.0,  # Cost requires per-model pricing lookup
        avg_tokens_per_run=round(avg_tokens, 1),
        avg_cost_per_run=0.0,
        runs_by_status=runs_by_status,
        top_models=[],
    )


@router.get(
    "/costs/runs/{run_id}",
    response_model=RunCostResponse,
    summary="Get cost breakdown for a specific run",
)
async def get_run_cost(
    run_id: str,
    api_key: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> RunCostResponse:
    """Get cost breakdown for a specific run.

    Note: Detailed per-agent cost breakdown requires runtime tracing
    data that is stored in Prometheus metrics, not the DB. This endpoint
    returns the run-level token total.
    """
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()

    if run is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )

    return RunCostResponse(
        run_id=run.id,
        total_tokens=run.tokens_used,
        total_cost_usd=0.0,
        breakdown=[],
    )
