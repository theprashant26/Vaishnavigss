"""
Simple IP-based rate limiter using Django's cache framework.

Usage:
    from core.utils.ratelimit import check_rate_limit
    if not check_rate_limit(request, 'contact', max_attempts=5, window_seconds=3600):
        # blocked

Phase 8 note: backed by DatabaseCache in prod (LocMemCache in dev), so
counters persist across gunicorn worker restarts and are shared across all
workers. The Phase 5 contract still holds; no caller-side change needed.
"""
from django.core.cache import cache

from .request_meta import get_client_ip


def check_rate_limit(
    request,
    key: str,
    max_attempts: int = 5,
    window_seconds: int = 3600,
) -> bool:
    """
    Returns True if the request is within the limit (allowed),
    False if it should be rejected.

    Uses a simple counter per (key, ip) with TTL = window_seconds.
    The counter increments on every call; once it exceeds max_attempts,
    we return False until the TTL expires.
    """
    ip = get_client_ip(request) or 'unknown'
    cache_key = f'ratelimit:{key}:{ip}'

    # add() is atomic: returns True only if the key was not already set.
    # If it returned True, we just created the counter with value 1.
    if cache.add(cache_key, 1, timeout=window_seconds):
        return True  # first hit in this window — always allowed

    try:
        count = cache.incr(cache_key)
    except ValueError:
        # Key expired between add() and incr() — treat as first hit again.
        cache.set(cache_key, 1, timeout=window_seconds)
        return True

    return count <= max_attempts
