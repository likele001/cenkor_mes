"""企业微信回调 / OAuth 外网 URL 构建"""

from __future__ import annotations

from app.core.config import settings as app_settings


def get_public_base_url(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    return (cfg.get("api_public_base_url") or app_settings.PUBLIC_BASE_URL or "").strip().rstrip("/")


def get_oauth_redirect_uri(cfg: dict | None = None) -> str:
    base = get_public_base_url(cfg)
    if not base:
        return ""
    return f"{base}/api/wecom/oauth/callback"


def get_events_callback_url(cfg: dict | None = None) -> str:
    base = get_public_base_url(cfg)
    if not base:
        return ""
    return f"{base}/api/wecom/callback"
