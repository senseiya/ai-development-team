"""Agent-level tracing — timing and metrics per agent execution.

Wraps agent runs with timing and records metrics to Prometheus.
"""

from __future__ import annotations

import time
from typing import Any

from core.observability.logging import get_logger
from core.observability.metrics import (
    AGENT_ERRORS,
    AGENT_LATENCY,
    AGENT_TOKENS_TOTAL,
    RUNS_ACTIVE,
    RUNS_TOTAL,
)

logger = get_logger(__name__)


class AgentTracer:
    """Context manager for tracing agent execution with Prometheus metrics."""

    def __init__(self, agent_name: str, run_id: str = "") -> None:
        self.agent_name = agent_name
        self.run_id = run_id
        self.start_time: float = 0.0
        self.tokens_used: int = 0
        self.provider: str = ""
        self.model: str = ""

    def __enter__(self) -> AgentTracer:
        self.start_time = time.perf_counter()
        RUNS_ACTIVE.inc()
        logger.info(
            "agent_started",
            agent=self.agent_name,
            run_id=self.run_id,
        )
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        elapsed = time.perf_counter() - self.start_time
        RUNS_ACTIVE.dec()

        AGENT_LATENCY.labels(agent=self.agent_name).observe(elapsed)

        if exc_type is not None:
            AGENT_ERRORS.labels(
                agent=self.agent_name,
                error_type=exc_type.__name__,
            ).inc()
            logger.error(
                "agent_failed",
                agent=self.agent_name,
                run_id=self.run_id,
                error=str(exc_val),
                duration_s=round(elapsed, 3),
            )
        else:
            logger.info(
                "agent_completed",
                agent=self.agent_name,
                run_id=self.run_id,
                duration_s=round(elapsed, 3),
                tokens=self.tokens_used,
                provider=self.provider,
                model=self.model,
            )

    def record_tokens(self, tokens: int, provider: str = "", model: str = "") -> None:
        """Record token usage after agent completes."""
        self.tokens_used = tokens
        self.provider = provider
        self.model = model

        if provider and model:
            AGENT_TOKENS_TOTAL.labels(
                agent=self.agent_name,
                provider=provider,
                model=model,
            ).inc(tokens)


def trace_run(run_id: str) -> RunTracer:
    """Create a tracer for an entire run (multiple agents)."""
    return RunTracer(run_id)


class RunTracer:
    """Traces an entire run from start to finish."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.start_time: float = 0.0
        self.status: str = "running"

    def __enter__(self) -> RunTracer:
        self.start_time = time.perf_counter()
        RUNS_ACTIVE.inc()
        logger.info("run_started", run_id=self.run_id)
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        elapsed = time.perf_counter() - self.start_time
        RUNS_ACTIVE.dec()

        if exc_type is not None:
            self.status = "failed"
        RUNS_TOTAL.labels(status=self.status).inc()

        logger.info(
            "run_completed",
            run_id=self.run_id,
            status=self.status,
            duration_s=round(elapsed, 3),
        )
