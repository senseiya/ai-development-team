"""FastAPI middleware for Prometheus HTTP metrics and structured request logging."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.observability.logging import get_logger
from core.observability.metrics import HTTP_REQUEST_LATENCY, HTTP_REQUESTS_TOTAL

logger = get_logger(__name__)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect HTTP request metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        method = request.method
        path = request.url.path

        # Normalize path parameters to avoid high-cardinality labels
        normalized = self._normalize_path(path)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        status_code = response.status_code
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=normalized,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_LATENCY.labels(
            method=method,
            endpoint=normalized,
        ).observe(elapsed)

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Replace UUIDs and numeric IDs with placeholders."""
        parts = path.split("/")
        normalized: list[str] = []
        for part in parts:
            # UUID pattern (36 chars with 4 dashes)
            is_uuid = (
                (len(part) == 36 and part.count("-") == 4)
                or (len(part) == 32 and all(c in "0123456789abcdef" for c in part))
                or part.isdigit()
                or (len(part) > 10 and "-" in part and all(c in "0123456789abcdef-" for c in part))
            )
            if is_uuid:
                normalized.append("{id}")
            else:
                normalized.append(part)
        return "/".join(normalized)
