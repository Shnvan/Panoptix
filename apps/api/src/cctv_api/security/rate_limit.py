"""In-memory sliding-window rate limiter (§16.17).

Provides per-key (IP or identity) rate limiting for sensitive
endpoints such as viewer-token minting and gateway ingest-token
minting.  The limiter uses a simple sliding-window counter stored
in an in-process dict — no external dependency (Redis, Memcached).

Thread-safety: the dict is guarded by a threading.Lock so that
concurrent ASGI workers in the same process share a single window.
Multi-process deployments get independent windows per process, which
is acceptable for the MVP rate-limit layer (Cloudflare is the
primary enforcement layer).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """Tuning knobs for one endpoint's rate limit."""

    max_requests: int
    window_seconds: int


@dataclass
class _WindowEntry:
    timestamps: list[float] = field(default_factory=list)


class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._windows: dict[str, _WindowEntry] = defaultdict(_WindowEntry)
        self._lock = threading.Lock()

    def check(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        """Return whether ``key`` is within its rate limit.

        Returns a ``RateLimitResult`` indicating whether the request
        is allowed plus the number of remaining requests and the
        retry-after delay (if blocked).
        """
        now = time.monotonic()
        cutoff = now - config.window_seconds

        with self._lock:
            entry = self._windows[key]
            # Prune timestamps outside the window
            entry.timestamps = [t for t in entry.timestamps if t > cutoff]

            if len(entry.timestamps) >= config.max_requests:
                oldest = entry.timestamps[0] if entry.timestamps else now
                retry_after = max(1, int(oldest + config.window_seconds - now) + 1)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=retry_after,
                )

            entry.timestamps.append(now)
            remaining = max(0, config.max_requests - len(entry.timestamps))
            return RateLimitResult(allowed=True, remaining=remaining, retry_after=0)

    def reset(self) -> None:
        """Clear all stored windows (useful in tests)."""
        with self._lock:
            self._windows.clear()


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


# ── Singleton limiter shared across the app ──
_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter
