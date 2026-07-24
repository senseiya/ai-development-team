"""Prometheus metrics for agent performance and system health.

Defines and registers all application metrics:
- Agent latency (per agent name)
- Token usage (per agent, provider, model)
- LLM provider call latency
- Error counts (per agent, error type)
- Run completion counters
- HTTP request metrics
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ---------------------------------------------------------------------------
# Agent metrics
# ---------------------------------------------------------------------------

AGENT_LATENCY = Histogram(
    "ai_agent_latency_seconds",
    "Time spent executing an agent (seconds)",
    ["agent"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

AGENT_TOKENS_TOTAL = Counter(
    "ai_agent_tokens_total",
    "Total tokens consumed by each agent",
    ["agent", "provider", "model"],
)

AGENT_ERRORS = Counter(
    "ai_agent_errors_total",
    "Total errors per agent",
    ["agent", "error_type"],
)

# ---------------------------------------------------------------------------
# Run metrics
# ---------------------------------------------------------------------------

RUNS_TOTAL = Counter(
    "ai_runs_total",
    "Total number of runs",
    ["status"],
)

RUNS_ACTIVE = Gauge(
    "ai_runs_active",
    "Number of currently running runs",
)

# ---------------------------------------------------------------------------
# LLM provider metrics
# ---------------------------------------------------------------------------

LLM_CALL_LATENCY = Histogram(
    "ai_llm_call_latency_seconds",
    "Time spent in LLM API calls (seconds)",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)

LLM_CALLS_TOTAL = Counter(
    "ai_llm_calls_total",
    "Total LLM API calls",
    ["provider", "model", "status"],
)

# ---------------------------------------------------------------------------
# HTTP metrics (collected by middleware)
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "ai_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "ai_http_request_latency_seconds",
    "HTTP request latency (seconds)",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# ---------------------------------------------------------------------------
# Sandbox metrics
# ---------------------------------------------------------------------------

SANDBOX_EXECUTIONS = Counter(
    "ai_sandbox_executions_total",
    "Total sandbox command executions",
    ["exit_code"],
)

SANDBOX_LATENCY = Histogram(
    "ai_sandbox_latency_seconds",
    "Sandbox command execution time",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)

# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

APP_INFO = Info(
    "ai_development_team",
    "Application information",
)
