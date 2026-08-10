"""钉钉 OAuth / card-action 外网 URL"""

from __future__ import annotations

from app.core.config import settings as app_settings


def get_public_base_url(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    return (cfg.get("api_public_base_url") or app_settings.PUBLIC_BASE_URL or "").strip().rstrip("/")


def get_oauth_redirect_uri(cfg: dict | None = None) -> str:
    base = get_public_base_url(cfg)
    if not base:
        return ""
    return f"{base}/api/dingtalk/oauth/callback"


def get_card_action_base_url(cfg: dict | None = None) -> str:
    base = get_public_base_url(cfg)
    if not base:
        return ""
    return f"{base}/api/dingtalk/card-action"
