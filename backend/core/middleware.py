"""ASGI middleware for production observability.

Kept separate from main.py so the middleware itself is unit-testable
without spinning up the whole app configuration.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.metrics import REQUEST_COUNT, REQUEST_DURATION_SECONDS

logger = logging.getLogger("blip.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID (reusing an inbound one if a proxy already set
    it), logs method/path/status/duration for every request, and records
    Prometheus request-count/duration metrics. This is a structured,
    app-level complement to uvicorn's own access log — the request ID ties
    a single request's log lines together and lets clients correlate a
    response with server-side logs when reporting an issue.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_seconds = time.perf_counter() - start
        duration_ms = duration_seconds * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        # Prefer the matched route's path template (e.g. "/paper/{id}") over
        # the raw resolved path, so per-request path params never explode
        # metric cardinality. Falls back to the raw path for 404s, which
        # never match a route.
        route = request.scope.get("route")
        path_label = route.path if route is not None else request.url.path

        REQUEST_COUNT.labels(method=request.method, path=path_label, status_code=response.status_code).inc()
        REQUEST_DURATION_SECONDS.labels(method=request.method, path=path_label).observe(duration_seconds)

        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )
        return response
