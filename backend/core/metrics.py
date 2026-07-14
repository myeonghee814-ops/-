"""Prometheus metrics, recorded by core/middleware.py and exposed at /metrics.

Uses the base `prometheus_client` library directly rather than a FastAPI/
Starlette wrapper package: those wrappers tend to pin a narrow Starlette
version range, which broke against this project's FastAPI pin the moment a
newer Starlette major version was published. `prometheus_client` has no
such coupling and `make_asgi_app()` mounts cleanly as a plain ASGI app.
"""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "path", "status_code"],
)

REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
