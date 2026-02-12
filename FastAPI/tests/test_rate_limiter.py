import time

from app.core.rate_limiter import InMemoryRateLimiter


def test_rate_limiter_allows_then_blocks_then_recovers():
    limiter = InMemoryRateLimiter()
    key = "ip:/auth/login"

    ok1, retry1 = limiter.allow(key, limit=2, window_seconds=1)
    ok2, retry2 = limiter.allow(key, limit=2, window_seconds=1)
    ok3, retry3 = limiter.allow(key, limit=2, window_seconds=1)

    assert ok1 is True and retry1 == 0
    assert ok2 is True and retry2 == 0
    assert ok3 is False
    assert retry3 >= 1

    time.sleep(1.05)
    ok4, retry4 = limiter.allow(key, limit=2, window_seconds=1)
    assert ok4 is True
    assert retry4 == 0
