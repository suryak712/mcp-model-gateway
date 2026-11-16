"""A per-client token-bucket rate limiter, so one agent cannot exhaust shared inference capacity."""

from __future__ import annotations

import time
from collections.abc import Callable


class RateLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self._capacity = float(per_minute)
        self._refill_per_sec = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # client -> (tokens, last_seen)

    def allow(self, client_id: str) -> bool:
        now = self._clock()
        tokens, last = self._buckets.get(client_id, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - last) * self._refill_per_sec)
        if tokens < 1.0:
            self._buckets[client_id] = (tokens, now)
            return False
        self._buckets[client_id] = (tokens - 1.0, now)
        return True
