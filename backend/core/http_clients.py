"""Shared, connection-pooled clients for outbound third-party calls.

Each external client module (services/external/*.py) previously opened a
brand-new httpx.AsyncClient or AsyncOpenAI instance — and therefore a new
TCP/TLS connection — on every single call. Under real load (e.g. the
export pipeline analyzing a dozen papers concurrently) that meant a fresh
handshake per request instead of reusing a warm connection pool.

These accessors are lazily-initialized module-level singletons, created on
first use and closed once at app shutdown via `aclose_all()` (wired into
main.py's lifespan). A single process only ever holds one pool per
provider, sized via Settings so production can tune it via env vars.
"""

import httpx
from openai import AsyncOpenAI

from core.config import get_settings

_http_client: httpx.AsyncClient | None = None
_openai_client: AsyncOpenAI | None = None


def get_http_client() -> httpx.AsyncClient:
    """Shared client for plain HTTP calls (Semantic Scholar, OpenAlex)."""
    global _http_client
    if _http_client is None:
        settings = get_settings()
        _http_client = httpx.AsyncClient(
            timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _http_client


def get_openai_client() -> AsyncOpenAI:
    """Shared OpenAI SDK client. Raises via the SDK if OPENAI_API_KEY is unset
    at call time; callers that need a friendlier error check the setting first."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS)
    return _openai_client


async def aclose_all() -> None:
    """Close every shared client. Call once, at app shutdown."""
    global _http_client, _openai_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
