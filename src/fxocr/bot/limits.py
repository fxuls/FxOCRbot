"""Abuse controls for a public bot: per-user sliding-window rate limit + a bounded global job gate."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager


class RateLimiter:
    """At most `limit` events per `window_s` per key. In-memory; resets on restart (fine for a bot)."""

    def __init__(self, limit: int, window_s: float, clock=time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._events: dict[int, deque[float]] = {}
        self._warned: dict[int, float] = {}

    def allow(self, key: int) -> bool:
        now = self._clock()
        q = self._events.setdefault(key, deque())
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        self._gc(now)
        return True

    def retry_after(self, key: int) -> int:
        q = self._events.get(key)
        if not q:
            return 0
        return max(1, int(self.window_s - (self._clock() - q[0])) + 1)

    def should_warn(self, key: int) -> bool:
        """Tell a throttled user once per window, not once per dropped image (albums!)."""
        now = self._clock()
        if now - self._warned.get(key, -1e9) >= self.window_s:
            self._warned[key] = now
            return True
        return False

    def _gc(self, now: float) -> None:
        if len(self._events) > 10_000:
            for k in [k for k, q in self._events.items() if not q or now - q[-1] >= self.window_s]:
                self._events.pop(k, None)
                self._warned.pop(k, None)


class Busy(Exception):
    pass


class JobGate:
    """Caps concurrent OCR jobs and the waiting queue so a flood can't exhaust the host."""

    def __init__(self, concurrency: int, queue_max: int):
        self._sem = asyncio.Semaphore(concurrency)
        self._queue_max = queue_max
        self._waiting = 0

    @asynccontextmanager
    async def slot(self):
        if self._waiting >= self._queue_max:
            raise Busy()
        self._waiting += 1
        try:
            await self._sem.acquire()
        finally:
            self._waiting -= 1
        try:
            yield
        finally:
            self._sem.release()
