"""Observability package — structured logging, Prometheus metrics, and tracing."""

from core.observability.health import router as health_router
from core.observability.logging import get_logger, setup_logging
from core.observability.metrics import (
    AGENT_ERRORS,
    AGENT_LATENCY,
    AGENT_TOKENS_TOTAL,
    APP_INFO,
    HTTP_REQUEST_LATENCY,
    HTTP_REQUESTS_TOTAL,
    LLM_CALL_LATENCY,
    LLM_CALLS_TOTAL,
    RUNS_ACTIVE,
    RUNS_TOTAL,
    SANDBOX_EXECUTIONS,
    SANDBOX_LATENCY,
)
from core.observability.middleware import PrometheusMiddleware
from core.observability.tracing import AgentTracer, RunTracer, trace_run

__all__ = [
    "AgentTracer",
    "RunTracer",
    "get_logger",
    "health_router",
    "setup_logging",
    "trace_run",
    "PrometheusMiddleware",
    "APP_INFO",
    "AGENT_LATENCY",
    "AGENT_TOKENS_TOTAL",
    "AGENT_ERRORS",
    "RUNS_TOTAL",
    "RUNS_ACTIVE",
    "LLM_CALL_LATENCY",
    "LLM_CALLS_TOTAL",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_LATENCY",
    "SANDBOX_EXECUTIONS",
    "SANDBOX_LATENCY",
]
