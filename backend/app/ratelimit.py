"""In-memory guards for the public endpoints.

Per-IP sliding window + a global daily cap so a bot can't run up the AI bill.
Counts live in process memory: with several server instances each keeps its own
counts (fine for a small site; move to Redis if traffic grows).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime


class RateLimiter:
    def __init__(self, limit: int, window_s: int, daily_limit: int):
        self.limit, self.window_s, self.daily_limit = limit, window_s, daily_limit
        self._hits: dict[str, deque] = defaultdict(deque)
        self._day = ""
        self._day_count = 0
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, str, int]:
        """Returns (allowed, reason, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        with self._lock:
            if today != self._day:
                self._day, self._day_count = today, 0
            if self._day_count >= self.daily_limit:
                return False, "daily", 3600
            q = self._hits[key]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False, "ip", int(self.window_s - (now - q[0])) + 1
            q.append(now)
            self._day_count += 1
            if len(self._hits) > 50_000:  # drop idle keys so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True, "", 0

    @property
    def used_today(self) -> int:
        return self._day_count
