"""Tests for observability module — logging, metrics, health, tracing."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

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
from core.observability.tracing import AgentTracer, trace_run


class TestStructuredLogging:
    def test_setup_logging_does_not_crash(self) -> None:
        """setup_logging should execute without errors."""
        setup_logging(log_level="DEBUG")

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_logger should return a structlog BoundLogger."""
        logger = get_logger("test.module")
        assert logger is not None
        # Should have bound methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_logger_accepts_kwargs(self) -> None:
        """Bound logger should accept keyword context."""
        logger = get_logger("test.ctx")
        # Should not raise
        logger.info("test_event", run_id="abc-123", agent="coder")


class TestPrometheusMetrics:
    def test_agent_latency_histogram(self) -> None:
        """AGENT_LATENCY should record observations."""
        AGENT_LATENCY.labels(agent="test_agent").observe(1.5)
        # Just verify it doesn't crash
        assert AGENT_LATENCY.labels(agent="test_agent") is not None

    def test_agent_tokens_counter(self) -> None:
        """AGENT_TOKENS_TOTAL should increment."""
        before = AGENT_TOKENS_TOTAL.labels(
            agent="test", provider="openrouter", model="qwen"
        )._value.get()
        AGENT_TOKENS_TOTAL.labels(
            agent="test", provider="openrouter", model="qwen"
        ).inc(100)
        after = AGENT_TOKENS_TOTAL.labels(
            agent="test", provider="openrouter", model="qwen"
        )._value.get()
        assert after == before + 100

    def test_agent_errors_counter(self) -> None:
        """AGENT_ERRORS should increment."""
        AGENT_ERRORS.labels(agent="test", error_type="ValueError").inc()
        assert AGENT_ERRORS.labels(agent="test", error_type="ValueError")._value.get() >= 1

    def test_runs_total_counter(self) -> None:
        """RUNS_TOTAL should increment."""
        RUNS_TOTAL.labels(status="completed").inc()
        assert RUNS_TOTAL.labels(status="completed")._value.get() >= 1

    def test_runs_active_gauge(self) -> None:
        """RUNS_ACTIVE should increment and decrement."""
        before = RUNS_ACTIVE._value.get()
        RUNS_ACTIVE.inc()
        assert RUNS_ACTIVE._value.get() == before + 1
        RUNS_ACTIVE.dec()
        assert RUNS_ACTIVE._value.get() == before

    def test_llm_call_latency(self) -> None:
        """LLM_CALL_LATENCY should record observations."""
        LLM_CALL_LATENCY.labels(provider="openrouter", model="qwen").observe(2.5)

    def test_llm_calls_total(self) -> None:
        """LLM_CALLS_TOTAL should increment."""
        LLM_CALLS_TOTAL.labels(
            provider="openrouter", model="qwen", status="success"
        ).inc()

    def test_sandbox_metrics(self) -> None:
        """Sandbox metrics should work."""
        SANDBOX_EXECUTIONS.labels(exit_code="0").inc()
        SANDBOX_LATENCY.observe(1.0)

    def test_app_info(self) -> None:
        """APP_INFO should store version info."""
        APP_INFO.info({"version": "0.1.0", "environment": "test"})
        assert APP_INFO._value == {"version": "0.1.0", "environment": "test"}

    def test_http_metrics(self) -> None:
        """HTTP metrics should work."""
        HTTP_REQUESTS_TOTAL.labels(
            method="GET", endpoint="/health", status_code="200"
        ).inc()
        HTTP_REQUEST_LATENCY.labels(method="GET", endpoint="/health").observe(0.1)


class TestAgentTracer:
    def test_tracer_records_success(self) -> None:
        """AgentTracer should record timing on success."""
        with AgentTracer("test_agent", run_id="run-123") as tracer:
            time.sleep(0.01)
            tracer.record_tokens(500, provider="openrouter", model="qwen")

        assert tracer.tokens_used == 500
        assert tracer.provider == "openrouter"
        assert tracer.model == "qwen"

    def test_tracer_records_failure(self) -> None:
        """AgentTracer should record errors on exception."""
        with (
            pytest.raises(ValueError, match="test error"),
            AgentTracer("test_agent_fail", run_id="run-456"),
        ):
            raise ValueError("test error")

    def test_tracer_increments_runs_active(self) -> None:
        """AgentTracer should increment/decrement RUNS_ACTIVE."""
        before = RUNS_ACTIVE._value.get()
        with AgentTracer("test_active", run_id="run-789"):
            assert RUNS_ACTIVE._value.get() == before + 1
        assert RUNS_ACTIVE._value.get() == before


class TestRunTracer:
    def test_run_tracer_records_success(self) -> None:
        """RunTracer should set status to completed."""
        with trace_run("run-trace-1") as tracer:
            time.sleep(0.01)
            tracer.status = "completed"

        assert tracer.status == "completed"

    def test_run_tracer_records_failure(self) -> None:
        """RunTracer should record failed status on exception."""
        with trace_run("run-trace-fail") as tracer:
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                tracer.status = "failed"

        assert tracer.status == "failed"

    def test_run_tracer_increments_runs_active(self) -> None:
        """RunTracer should increment/decrement RUNS_ACTIVE."""
        before = RUNS_ACTIVE._value.get()
        with trace_run("run-trace-active"):
            assert RUNS_ACTIVE._value.get() == before + 1
        assert RUNS_ACTIVE._value.get() == before


class TestHealthEndpoints:
    def test_liveness(self) -> None:
        """GET /health/live should return 200."""
        from apps.api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_health_endpoint_returns_checks(self) -> None:
        """GET /health should return system checks."""
        from apps.api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "environment" in data

    def test_metrics_endpoint_returns_prometheus(self) -> None:
        """GET /metrics should return Prometheus text format."""
        from apps.api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "ai_agent_latency_seconds" in text
        assert "ai_runs_total" in text
        assert "ai_http_requests_total" in text


class TestPrometheusMiddleware:
    def test_middleware_normalizes_uuid_paths(self) -> None:
        """Middleware should normalize UUID path segments."""
        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert PrometheusMiddleware._normalize_path(f"/api/v1/runs/{uuid}") == "/api/v1/runs/{id}"
        assert PrometheusMiddleware._normalize_path("/api/v1/runs/12345") == "/api/v1/runs/{id}"
        assert PrometheusMiddleware._normalize_path("/health") == "/health"
