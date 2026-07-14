import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Minimal in-process, time-expiring cache.

    Deliberately dependency-free for this stage of the project. If the app
    grows beyond a single process (e.g. multiple API instances behind a load
    balancer), swap this for a Redis-backed implementation behind the same
    get/set interface — nothing calling it needs to change.
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 256) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: T) -> None:
        if key not in self._store and len(self._store) >= self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]

        self._store[key] = (time.monotonic() + self._ttl_seconds, value)
