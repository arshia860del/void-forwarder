"""
In-memory LRU Deduplication Cache with TTL expiration.
Prevents duplicate notifications across network retries and event re-deliveries.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Tuple


class DeduplicationCache:
    """Thread-safe Least Recently Used (LRU) Cache with Time-To-Live (TTL)."""

    def __init__(self, max_size: int = 2000, ttl_seconds: int = 3600):
        self.max_size = max(1, max_size)
        self.ttl_seconds = max(1, ttl_seconds)
        self._cache: OrderedDict[Tuple[int, int], float] = OrderedDict()
        self._lock = Lock()

    def is_duplicate(self, chat_id: int, message_id: int) -> bool:
        """Check if (chat_id, message_id) has already been processed."""
        key = (chat_id, message_id)
        now = time.monotonic()

        with self._lock:
            if key in self._cache:
                timestamp = self._cache[key]
                if now - timestamp < self.ttl_seconds:
                    self._cache.move_to_end(key)
                    return True
                else:
                    del self._cache[key]

            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = now
            return False

    def remove(self, chat_id: int, message_id: int) -> None:
        """Remove key from cache in case of delivery failure."""
        key = (chat_id, message_id)
        with self._lock:
            self._cache.pop(key, None)

    def size(self) -> int:
        """Return the current number of tracked message keys."""
        with self._lock:
            return len(self._cache)
