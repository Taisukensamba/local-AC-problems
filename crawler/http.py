from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float,
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        self._min_interval = 1.0 / requests_per_second
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._next_allowed = 0.0

    def wait(self) -> None:
        now = self._time_fn()
        if now < self._next_allowed:
            self._sleep_fn(self._next_allowed - now)
        self._next_allowed = self._time_fn() + self._min_interval


@dataclass
class CacheConfig:
    enabled: bool
    ttl_sec: int
    dir_path: Path


class HttpClient:
    def __init__(
        self,
        requests_per_second: float,
        cache: CacheConfig,
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._limiter = RateLimiter(requests_per_second, time_fn=time_fn, sleep_fn=sleep_fn)
        self._cache = cache
        self._time_fn = time_fn
        self._user_agent = "AC-problems/0.1 (+https://github.com/your-org/ac-problems)"

    def get_text(self, url: str, headers: dict | None = None, use_cache: bool = True) -> str:
        self._limiter.wait()
        use_cache = (
            use_cache
            and self._cache.enabled
            and not _has_cookie(headers)
            and not url.startswith("file://")
        )
        cache_path = self._cache.dir_path / f"{_cache_key(url)}.json"
        if use_cache:
            cached = _load_cache(cache_path, self._cache.ttl_sec, self._time_fn)
            if cached is not None:
                return cached
        base_headers = {"User-Agent": self._user_agent}
        if headers:
            base_headers.update(headers)
        req = Request(url, headers=base_headers)
        with urlopen(req) as res:
            body = res.read().decode("utf-8")
        if use_cache:
            _store_cache(cache_path, body, self._time_fn)
        return body


def _has_cookie(headers: dict | None) -> bool:
    if not headers:
        return False
    return any(key.lower() == "cookie" for key in headers)


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _load_cache(path: Path, ttl_sec: int, time_fn: Callable[[], float]) -> str | None:
    if ttl_sec <= 0 or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = payload.get("ts")
    body = payload.get("body")
    if ts is None or body is None:
        return None
    if time_fn() - ts > ttl_sec:
        return None
    return body


def _store_cache(path: Path, body: str, time_fn: Callable[[], float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": time_fn(), "body": body}
    path.write_text(json.dumps(payload), encoding="utf-8")


def default_cache_config() -> CacheConfig:
    enabled = os.getenv("AC_CACHE_ENABLED", "true").lower() == "true"
    ttl_sec = int(os.getenv("AC_CACHE_TTL_SEC", "3600"))
    dir_path = Path(os.getenv("AC_CACHE_DIR", "data/cache"))
    return CacheConfig(enabled=enabled, ttl_sec=ttl_sec, dir_path=dir_path)


def cache_config_from_app(config) -> CacheConfig:
    return CacheConfig(
        enabled=config.cache.enabled,
        ttl_sec=config.cache.ttl_sec,
        dir_path=Path(config.cache.dir_path),
    )
