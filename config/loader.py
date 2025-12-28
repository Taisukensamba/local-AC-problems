from __future__ import annotations

from dataclasses import dataclass
import os
import tomllib


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SyncConfig:
    mode: str


@dataclass(frozen=True)
class DifficultyConfig:
    source_url: str


@dataclass(frozen=True)
class CookieConfig:
    revel_session: str | None


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool
    ttl_sec: int
    dir_path: str


@dataclass(frozen=True)
class AppConfig:
    user_id: str
    sync: SyncConfig
    rate_limit: float
    difficulty: DifficultyConfig
    cookie: CookieConfig
    cache: CacheConfig


def _get_required(table: dict, key: str) -> object:
    if key not in table:
        raise ConfigError(f"config: missing '{key}'")
    return table[key]


def _expect_str(value: object, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"config: '{key}' must be a non-empty string")
    return value


def _expect_number(value: object, key: str) -> float:
    if not isinstance(value, (int, float)):
        raise ConfigError(f"config: '{key}' must be a number")
    return float(value)


def _expect_bool(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"config: '{key}' must be a boolean")
    return value


def _expect_int(value: object, key: str) -> int:
    if not isinstance(value, int):
        raise ConfigError(f"config: '{key}' must be an integer")
    return value


def load_config(path: str | None = None) -> AppConfig:
    config_path = path or os.getenv("AC_CONFIG_PATH", "config/config.toml")
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as exc:
        raise ConfigError(f"config: file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config: invalid toml: {exc}") from exc

    user_id_env = os.getenv("AC_USER_ID")
    if user_id_env is not None and user_id_env.strip():
        user_id = _expect_str(user_id_env, "AC_USER_ID")
    else:
        user_id = _expect_str(_get_required(data, "user_id"), "user_id")
    rate_limit = _expect_number(_get_required(data, "rate_limit"), "rate_limit")
    if rate_limit <= 0:
        raise ConfigError("config: 'rate_limit' must be > 0")

    sync_raw = _get_required(data, "sync")
    if not isinstance(sync_raw, dict):
        raise ConfigError("config: 'sync' must be a table")
    mode = _expect_str(_get_required(sync_raw, "mode"), "sync.mode")
    allowed_modes = {"api", "cookie", "hybrid"}
    if mode not in allowed_modes:
        allowed = ", ".join(sorted(allowed_modes))
        raise ConfigError(f"config: 'sync.mode' must be one of {allowed}")

    difficulty_raw = data.get("difficulty", {})
    if difficulty_raw and not isinstance(difficulty_raw, dict):
        raise ConfigError("config: 'difficulty' must be a table")
    source_url_env = os.getenv("AC_DIFFICULTY_SOURCE_URL")
    if source_url_env is not None and source_url_env.strip():
        source_url = _expect_str(source_url_env, "AC_DIFFICULTY_SOURCE_URL")
    else:
        source_url = _expect_str(
            difficulty_raw.get(
                "source_url",
                "https://kenkoooo.com/atcoder/resources/problem-models.json",
            ),
            "difficulty.source_url",
        )

    cookie_raw = data.get("cookie", {})
    if cookie_raw and not isinstance(cookie_raw, dict):
        raise ConfigError("config: 'cookie' must be a table")
    revel_session_env = os.getenv("AC_REVEL_SESSION")
    if revel_session_env is not None and revel_session_env.strip():
        revel_session = _expect_str(revel_session_env, "AC_REVEL_SESSION")
    else:
        revel_session = cookie_raw.get("revel_session")
        if revel_session is not None:
            revel_session = _expect_str(revel_session, "cookie.revel_session")
    if not revel_session:
        raise ConfigError("config: missing 'cookie.revel_session' or AC_REVEL_SESSION")

    cache_raw = data.get("cache", {})
    if cache_raw and not isinstance(cache_raw, dict):
        raise ConfigError("config: 'cache' must be a table")
    cache_enabled = cache_raw.get("enabled", True)
    cache_ttl = cache_raw.get("ttl_sec", 3600)
    cache_dir = cache_raw.get("dir_path", "data/cache")
    cache_enabled = _expect_bool(cache_enabled, "cache.enabled")
    cache_ttl = _expect_int(cache_ttl, "cache.ttl_sec")
    cache_dir = _expect_str(cache_dir, "cache.dir_path")

    return AppConfig(
        user_id=user_id,
        sync=SyncConfig(mode=mode),
        rate_limit=rate_limit,
        difficulty=DifficultyConfig(source_url=source_url),
        cookie=CookieConfig(revel_session=revel_session),
        cache=CacheConfig(enabled=cache_enabled, ttl_sec=cache_ttl, dir_path=cache_dir),
    )
