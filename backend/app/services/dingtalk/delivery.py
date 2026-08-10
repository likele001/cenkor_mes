"""钉钉个人推送可达性诊断"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dingtalk_push_log import DingtalkPushLog
from app.models.user import User
from app.services.dingtalk.settings import get_dingtalk_settings_admin, is_dingtalk_enabled


def build_delivery_diagnostics(db: Session) -> dict:
    enabled = is_dingtalk_enabled(db)
    cfg = get_dingtalk_settings_admin(db)
    bound = int(
        db.scalar(
            select(func.count(User.id)).where(
                User.is_active.is_(True),
                User.dingtalk_userid.isnot(None),
                User.dingtalk_userid != "",
            )
        )
        or 0
    )
    failed_24h = int(
        db.scalar(
            select(func.count(DingtalkPushLog.id)).where(
                DingtalkPushLog.status == "failed",
            )
        )
        or 0
    )
    return {
        "enabled": enabled,
        "configured": bool(cfg.get("app_key_configured") and cfg.get("app_secret_configured")),
        "bound_users": bound,
        "recent_failed": failed_24h,
        "oauth_redirect_url": cfg.get("oauth_redirect_url", ""),
    }
