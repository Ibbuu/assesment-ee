import threading
import time


class TTLCache:
    """Small in-memory cache so repeat lookups don't hit GitHub every time.
    """

    def __init__(self, ttl, max_entries=500):
        self.ttl = ttl
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries = {}

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None

            expires_at, value = entry
            if expires_at <= time.monotonic():
                del self._entries[key]
                return None

            return value

    def set(self, key, value):
        if self.ttl <= 0:
            return

        with self._lock:
            if len(self._entries) >= self.max_entries:
                self._entries.clear()
            self._entries[key] = (time.monotonic() + self.ttl, value)
