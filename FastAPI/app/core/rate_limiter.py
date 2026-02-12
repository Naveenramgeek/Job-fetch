import threading
import time


class InMemoryRateLimiter:
    """
    Simple in-memory fixed-window rate limiter.
    Good for single-instance deployments. For distributed setups, use Redis.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, tuple[int, float]] = {}

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        with self._lock:
            count, window_start = self._state.get(key, (0, now))
            if now - window_start >= window_seconds:
                count = 0
                window_start = now
            if count >= limit:
                retry_after = max(1, int(window_seconds - (now - window_start)))
                return False, retry_after
            self._state[key] = (count + 1, window_start)
            return True, 0


rate_limiter = InMemoryRateLimiter()
