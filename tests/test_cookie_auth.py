import unittest

from config.loader import (
    AppConfig,
    AtCoderConfig,
    CacheConfig,
    CodeforcesConfig,
    CookieConfig,
    ConfigError,
    DifficultyConfig,
    RateLimitConfig,
    SyncConfig,
)
from crawler.cookie_auth import build_cookie_header, require_revel_session


class CookieAuthTest(unittest.TestCase):
    def test_build_cookie_header(self) -> None:
        header = build_cookie_header("abc")
        self.assertEqual(header, "REVEL_SESSION=abc")

    def test_require_revel_session_missing(self) -> None:
        config = AppConfig(
            atcoder=AtCoderConfig(
                user_id="alice",
                sync=SyncConfig(mode="cookie"),
                difficulty=DifficultyConfig(source_url="https://example.com"),
                cookie=CookieConfig(revel_session=None),
            ),
            codeforces=CodeforcesConfig(handle="alice_cf", include_gym=False),
            rate_limit=RateLimitConfig(atcoder_rps=1.0, codeforces_min_interval_seconds=2.0),
            cache=CacheConfig(enabled=True, ttl_sec=3600, dir_path="data/cache"),
        )
        with self.assertRaises(ConfigError):
            require_revel_session(config)
