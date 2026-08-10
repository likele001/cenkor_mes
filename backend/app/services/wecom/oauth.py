"""企业微信 OAuth 绑定用户 userid"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.services.wecom.client import WecomApiError, get_access_token, get_userinfo_by_code
from app.services.wecom.settings import get_wecom_credentials, get_wecom_settings_raw
from app.services.wecom.urls import get_oauth_redirect_uri


def create_bind_state(*, tenant_id: int, user_id: int, minutes: int = 30) -> str:
    return create_access_token(
        {"purpose": "wecom_bind", "sub": str(user_id), "tenant_id": int(tenant_id)},
        expires_minutes=minutes,
    )


def parse_bind_state(state: str) -> tuple[int, int]:
    data = decode_token(state)
    if data.get("purpose") != "wecom_bind":
        raise ValueError("invalid bind state")
    return int(data["tenant_id"]), int(data["sub"])


def get_bind_authorize_url(db: Session, tenant_id: int, user_id: int) -> str:
    cfg = get_wecom_settings_raw(db, tenant_id)
    corp_id, _, _ = get_wecom_credentials(db, tenant_id)
    redirect_uri = get_oauth_redirect_uri(cfg)
    if not corp_id or not redirect_uri:
        raise ValueError("请先配置 CorpID 与 PUBLIC_BASE_URL（API 外网地址）")
    state = create_bind_state(tenant_id=tenant_id, user_id=user_id)
    from app.services.wecom.client import get_oauth_code_url
    return get_oauth_code_url(corp_id, redirect_uri, state)


def bind_user_with_code(db: Session, *, tenant_id: int, user_id: int, code: str) -> User:
    corp_id, corp_secret, _ = get_wecom_credentials(db, tenant_id)
    if not corp_id or not corp_secret:
        raise ValueError("企业微信应用未配置")
    token = get_access_token(corp_id, corp_secret)
    info = get_userinfo_by_code(token, code)
    userid = (info.get("UserId") or "").strip()
    if not userid:
        raise ValueError("未获取到企业微信 userid")
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise ValueError("用户不存在")
    user.wecom_userid = userid
    user.wecom_bound_at = datetime.utcnow()
    db.flush()
    from app.services.wecom.welcome import send_bind_welcome
    send_bind_welcome(db, tenant_id, userid)
    return user


def get_user_by_wecom_userid(db: Session, tenant_id: int, userid: str) -> User | None:
    uid = (userid or "").strip()
    if not uid:
        return None
    return db.scalar(
        select(User).where(
            User.wecom_userid == uid,
            User.is_active.is_(True),
        )
    )
