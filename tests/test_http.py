import unittest

from crawler.http import RateLimiter


class RateLimiterTest(unittest.TestCase):
    def test_rate_limiter_waits(self) -> None:
        now = 0.0
        slept = []

        def time_fn() -> float:
            return now

        def sleep_fn(seconds: float) -> None:
            nonlocal now
            slept.append(seconds)
            now += seconds

        limiter = RateLimiter(2.0, time_fn=time_fn, sleep_fn=sleep_fn)
        limiter.wait()
        limiter.wait()
        limiter.wait()

        self.assertGreaterEqual(sum(slept), 1.0)
