"""In-memory query result cache to avoid repeated Athena queries."""
from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

_cache: dict = {}
DEFAULT_TTL = 600  # 10 minutes


def cached_query(key_prefix: str, ttl: int = DEFAULT_TTL) -> Callable:
    """Decorator: cache function result in memory for `ttl` seconds.

    Cache key is built from key_prefix + str(args) + str(kwargs).
    Thread-safe enough for Flask's threaded mode (dict ops are atomic in CPython).

    Usage:
        @cached_query("athena:summary")
        def fetch_summary(date_from=None, date_to=None):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            parts = [key_prefix]
            for a in args:
                parts.append(str(a))
            for k, v in sorted(kwargs.items()):
                if v is not None:
                    parts.append(f"{k}={v}")
            cache_key = ":".join(parts)

            now = time.time()
            entry = _cache.get(cache_key)
            if entry and now - entry["ts"] < ttl:
                logger.debug("Cache hit: %s (age=%.0fs)", cache_key, now - entry["ts"])
                return entry["value"]

            result = func(*args, **kwargs)
            _cache[cache_key] = {"value": result, "ts": now}
            logger.debug("Cache miss: %s (stored, ttl=%ds)", cache_key, ttl)
            return result
        return wrapper
    return decorator


def invalidate(prefix: str = ""):
    """Clear all cache entries matching prefix. Empty prefix = clear all."""
    if not prefix:
        _cache.clear()
        logger.info("Query cache cleared (all)")
        return
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]
    logger.info("Query cache cleared: %d keys matching '%s'", len(keys), prefix)


def stats() -> dict:
    """Return cache stats."""
    now = time.time()
    total = len(_cache)
    fresh = sum(1 for e in _cache.values() if now - e["ts"] < DEFAULT_TTL)
    return {"total_entries": total, "fresh_entries": fresh, "stale_entries": total - fresh}
