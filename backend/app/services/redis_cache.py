"""Redis caching layer for hot data (Phase 3)."""
from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Callable, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def is_available() -> bool:
    return settings.redis_enabled


def get_client():
    """Lazy-init Redis client."""
    global _client
    if _client is None:
        try:
            import redis
            _client = redis.from_url(settings.redis_url, decode_responses=True)
            _client.ping()
            logger.info("Redis connected: %s", settings.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable: %s", e)
            _client = None
    return _client


def get(key: str) -> Optional[dict]:
    """Get cached value as dict (JSON-deserialized)."""
    if not is_available():
        return None
    client = get_client()
    if not client:
        return None
    try:
        val = client.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.warning("Redis get failed for '%s': %s", key, e)
        return None


def set(key: str, value: dict, ttl: int = None):
    """Set cached value (JSON-serialized) with TTL."""
    if not is_available():
        return
    client = get_client()
    if not client:
        return
    try:
        if ttl is None:
            ttl = settings.redis_default_ttl
        client.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("Redis set failed for '%s': %s", key, e)


def delete(key: str):
    """Delete a cached key."""
    if not is_available():
        return
    client = get_client()
    if client:
        try:
            client.delete(key)
        except Exception:
            pass


def invalidate_pattern(pattern: str):
    """Delete all keys matching pattern (e.g., 'analysis:*')."""
    if not is_available():
        return
    client = get_client()
    if not client:
        return
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
            logger.info("Invalidated %d keys matching '%s'", len(keys), pattern)
    except Exception as e:
        logger.warning("Redis invalidate failed: %s", e)


def cached(key_prefix: str, ttl: int = None) -> Callable:
    """Decorator: cache function result in Redis.

    Usage:
        @cached("analysis:summary")
        def get_summary(...):
            ...

        @cached("analysis:effect:{metric}")
        def get_effect(metric="like_count"):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from prefix + args
            key_parts = [key_prefix]
            for a in args:
                key_parts.append(str(a))
            for k, v in sorted(kwargs.items()):
                if v is not None:
                    key_parts.append(f"{k}={v}")
            cache_key = ":".join(key_parts)

            # Try cache
            cached_val = get(cache_key)
            if cached_val is not None:
                return cached_val

            # Compute
            result = func(*args, **kwargs)

            # Store
            if result is not None:
                set(cache_key, result, ttl)

            return result
        return wrapper
    return decorator
