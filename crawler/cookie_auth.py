from __future__ import annotations

from config.loader import AppConfig, ConfigError


def require_revel_session(config: AppConfig) -> str:
    revel_session = config.cookie.revel_session
    if not revel_session:
        raise ConfigError("login required: set cookie.revel_session in config")
    return revel_session


def build_cookie_header(revel_session: str) -> str:
    return f"REVEL_SESSION={revel_session}"
