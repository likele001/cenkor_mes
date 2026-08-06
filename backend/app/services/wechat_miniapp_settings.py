from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY_APP_ID = "wechat_miniapp.app_id"
KEY_APP_SECRET = "wechat_miniapp.app_secret"

SECRET_MASK = "********"


def _env_fallback() -> tuple[str, str]:
    return (
        (os.getenv("WX_MINIAPP_APPID") or "").strip(),
        (os.getenv("WX_MINIAPP_SECRET") or "").strip(),
    )


def get_wechat_miniapp_credentials(db: Session, tenant_id: int) -> tuple[str, str]:
    row_id = get_setting(db, tenant_id, KEY_APP_ID)
    row_secret = get_setting(db, tenant_id, KEY_APP_SECRET)
    app_id = (row_id.value or "").strip() if row_id and row_id.value else ""
    secret = (row_secret.value or "").strip() if row_secret and row_secret.value else ""
    if not app_id or not secret:
        env_id, env_secret = _env_fallback()
        app_id = app_id or env_id
        secret = secret or env_secret
    return app_id, secret


def get_wechat_miniapp_settings_admin(db: Session, tenant_id: int) -> dict:
    app_id, secret = get_wechat_miniapp_credentials(db, tenant_id)
    env_id, _ = _env_fallback()
    return {
        "app_id": app_id,
        "app_secret_configured": bool(secret),
        "app_secret_masked": SECRET_MASK if secret else "",
        "env_fallback_app_id": env_id or None,
    }


def save_wechat_miniapp_settings(db: Session, tenant_id: int, payload: dict) -> dict:
    app_id = (payload.get("app_id") or "").strip()
    app_secret = payload.get("app_secret")

    if app_id:
        upsert_setting(db, tenant_id, KEY_APP_ID, app_id)
    elif payload.get("clear_app_id"):
        upsert_setting(db, tenant_id, KEY_APP_ID, "")

    if app_secret is not None:
        secret_str = str(app_secret).strip()
        if secret_str and secret_str != SECRET_MASK:
            upsert_setting(db, tenant_id, KEY_APP_SECRET, secret_str)
        elif secret_str == "":
            upsert_setting(db, tenant_id, KEY_APP_SECRET, "")

    return get_wechat_miniapp_settings_admin(db, tenant_id)
