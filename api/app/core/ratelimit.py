"""Small in-memory sliding-window rate limiter (per client IP and route).

Single-process only, which matches the one-worker deployment. Swap for Redis if scaled out.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def rate_limit(limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{ip}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many requests, please wait a moment.",
                    headers={"Retry-After": str(window_seconds)},
                )
            q.append(now)

    return dependency
