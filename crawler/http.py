from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

import random
import requests


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


class AdaptiveThrottler:
    def __init__(
        self,
        min_delay: float = 0.50,
        max_delay: float = 5.00,
        delay: float = 0.50,
        jitter: float = 0.15,
        backoff_factor: float = 2.0,
        recovery_factor: float = 0.90,
        success_streak_for_speedup: int = 5,
        error_streak_for_slowdown: int = 1,
        max_decrease: float = 0.05,
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.delay = delay
        self.jitter = jitter
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.success_streak_for_speedup = success_streak_for_speedup
        self.error_streak_for_slowdown = error_streak_for_slowdown
        self.max_decrease = max_decrease
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._rng = rng or random.Random()
        self._success_streak = 0
        self._error_streak = 0

    def sleep_before_request(self) -> None:
        jitter = self._rng.uniform(1.0 - self.jitter, 1.0 + self.jitter)
        self._sleep_fn(self.delay * jitter)

    def on_success(self, _resp, _latency_ms: int) -> None:
        self._success_streak += 1
        self._error_streak = 0
        if self._success_streak < self.success_streak_for_speedup:
            return
        self._success_streak = 0
        new_delay = max(self.min_delay, self.delay * self.recovery_factor)
        if self.max_decrease is not None:
            new_delay = max(new_delay, self.delay - self.max_decrease)
        self.delay = new_delay

    def on_failure(self, kind: str) -> None:
        self._error_streak += 1
        self._success_streak = 0
        if self._error_streak < self.error_streak_for_slowdown:
            return
        penalty = self.backoff_factor
        if kind in {"rate_limited", "forbidden"}:
            penalty *= 1.5
        elif kind == "suspected_block":
            penalty *= 1.2
        self.delay = min(self.max_delay, self.delay * penalty)


class LoginRequiredError(RuntimeError):
    def __init__(self, url: str) -> None:
        super().__init__(f"login required: {url}")
        self.url = url


class FetchError(RuntimeError):
    def __init__(self, url: str, status: int | None, kind: str) -> None:
        super().__init__(f"fetch failed ({kind}) for {url}")
        self.url = url
        self.status = status
        self.kind = kind


def classify_response(resp: requests.Response, body_snippet: str) -> str:
    status = resp.status_code
    if status == 429:
        return "rate_limited"
    if status == 403:
        return "forbidden"
    if 500 <= status <= 599:
        return "server_error"
    if 300 <= status <= 399:
        location = resp.headers.get("Location", "")
        if "/login" in location:
            return "login_required"
        return "redirect"
    if status != 200:
        return "http_error"
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return "success"
    snippet = body_snippet or ""
    snippet_lower = snippet.lower()
    login_markers = [
        "action=\"/login\"",
        "name=\"username\"",
        "sign in",
    ]
    if any(marker in snippet_lower for marker in login_markers) or "ログイン" in snippet:
        return "login_required"
    stripped = snippet.strip()
    if not stripped or len(stripped) < 200:
        return "suspected_block"
    block_markers = [
        "cloudflare",
        "cf-ray",
        "attention required",
        "robot check",
        "bot detection",
        "access denied",
    ]
    if any(marker in snippet_lower for marker in block_markers):
        return "suspected_block"
    return "success"


class AdaptiveHttpClient:
    def __init__(
        self,
        cache: CacheConfig,
        throttler: AdaptiveThrottler | None = None,
        session: requests.Session | None = None,
        time_fn: Callable[[], float] = time.time,
        timeout_sec: int = 10,
        max_retries: int = 5,
    ) -> None:
        self._cache = cache
        self._throttler = throttler or AdaptiveThrottler()
        self._session = session or requests.Session()
        self._time_fn = time_fn
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "ja,en;q=0.8",
            }
        )

    def get_text(self, url: str, headers: dict | None = None, use_cache: bool = True) -> str:
        if url.startswith("file://"):
            path = url[len("file://") :]
            return Path(path).read_text(encoding="utf-8")
        use_cache = use_cache and self._cache.enabled and not _has_cookie(headers)
        cache_path = self._cache.dir_path / f"{_cache_key(url)}.json"
        if use_cache:
            cached = _load_cache(cache_path, self._cache.ttl_sec, self._time_fn)
            if cached is not None:
                return cached
        merged_headers = dict(headers or {})
        for attempt in range(self._max_retries + 1):
            self._throttler.sleep_before_request()
            start = self._time_fn()
            try:
                resp = self._session.get(url, headers=merged_headers, timeout=self._timeout_sec)
            except requests.RequestException:
                latency_ms = int((self._time_fn() - start) * 1000)
                self._throttler.on_failure("network_error")
                print(
                    f"[ERR network_error] delay->{self._throttler.delay:.2f}s "
                    f"latency={latency_ms}ms retry={attempt + 1} url={_shorten_url(url)}"
                )
                if attempt >= self._max_retries:
                    raise FetchError(url, None, "network_error")
                continue
            latency_ms = int((self._time_fn() - start) * 1000)
            body = resp.text
            snippet = body[:4096]
            kind = classify_response(resp, snippet)
            short_url = _shorten_url(url)
            if kind == "success":
                self._throttler.on_success(resp, latency_ms)
                print(
                    f"[OK] status={resp.status_code} delay={self._throttler.delay:.2f}s "
                    f"latency={latency_ms}ms url={short_url}"
                )
                if use_cache:
                    _store_cache(cache_path, body, self._time_fn)
                return body
            if kind == "login_required":
                print(
                    f"[{resp.status_code} {kind}] delay={self._throttler.delay:.2f}s "
                    f"latency={latency_ms}ms url={short_url}"
                )
                raise LoginRequiredError(url)
            if kind == "http_error":
                print(
                    f"[{resp.status_code} {kind}] delay={self._throttler.delay:.2f}s "
                    f"latency={latency_ms}ms url={short_url}"
                )
                raise HTTPError(url, resp.status_code, resp.reason, resp.headers, None)
            before_delay = self._throttler.delay
            self._throttler.on_failure(kind)
            print(
                f"[{resp.status_code} {kind}] delay->{self._throttler.delay:.2f}s "
                f"latency={latency_ms}ms retry={attempt + 1} url={short_url}"
            )
            if attempt >= self._max_retries:
                raise FetchError(url, resp.status_code, kind)
            if kind not in {"rate_limited", "forbidden", "suspected_block", "server_error"}:
                raise FetchError(url, resp.status_code, kind)
            if self._throttler.delay <= before_delay:
                self._throttler.delay = min(self._throttler.max_delay, before_delay * 2)
        raise FetchError(url, None, "retry_exhausted")


def _shorten_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    short = parsed.path
    if parsed.query:
        short = f"{short}?{parsed.query}"
    return short or url


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
