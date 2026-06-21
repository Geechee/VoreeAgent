"""Simple in-memory cache with TTL for expensive read operations."""
import time
import threading
from typing import Any, Optional


class TTLCache:
    def __init__(self, default_ttl: int = 30):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = default_ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires, value = entry
            if time.monotonic() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        with self._lock:
            expires = time.monotonic() + (ttl or self._ttl)
            self._store[key] = (expires, value)

    def invalidate(self, prefix: str = ""):
        with self._lock:
            if not prefix:
                self._store.clear()
            else:
                keys = [k for k in self._store if k.startswith(prefix)]
                for k in keys:
                    del self._store[k]


stats_cache = TTLCache(default_ttl=15)
