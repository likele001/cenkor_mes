"""钉钉 OAuth 绑定用户 userid"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.services.dingtalk.client import (
    DingtalkApiError,
    exchange_user_access_token,
    get_access_token,
    get_oauth_authorize_url,
    get_user_me,
    get_userid_by_unionid,
)
from app.services.dingtalk.settings import get_dingtalk_credentials, get_dingtalk_settings_raw
from app.services.dingtalk.urls import get_oauth_redirect_uri


def create_bind_state(*, user_id: int, minutes: int = 30) -> str:
    return create_access_token(
        {"purpose": "dingtalk_bind", "sub": str(user_id), "tenant_id": 1},
        expires_minutes=minutes,
    )


def parse_bind_state(state: str) -> tuple[int, int]:
    data = decode_token(state)
    if data.get("purpose") != "dingtalk_bind":
        raise ValueError("invalid bind state")
    return 1, int(data["sub"])


def get_bind_authorize_url(db: Session, user_id: int) -> str:
    cfg = get_dingtalk_settings_raw(db)
    _, app_key, _, _ = get_dingtalk_credentials(db)
    redirect_uri = get_oauth_redirect_uri(cfg)
    if not app_key or not redirect_uri:
        raise ValueError("请先配置 AppKey 与 PUBLIC_BASE_URL（API 外网地址）")
    state = create_bind_state(user_id=user_id)
    return get_oauth_authorize_url(app_key, redirect_uri, state)


def bind_user_with_code(db: Session, *, tenant_id: int = 1, user_id: int, code: str) -> User:
    # 单租户版：tenant_id 仅用于兼容遗留调用方，恒为 1
    _, app_key, app_secret, _ = get_dingtalk_credentials(db)
    if not app_key or not app_secret:
        raise ValueError("钉钉应用未配置")
    token_data = exchange_user_access_token(app_key, app_secret, code)
    user_access_token = str(token_data.get("accessToken") or "")
    if not user_access_token:
        raise ValueError("未获取到用户 accessToken")
    me = get_user_me(user_access_token)
    union_id = (me.get("unionId") or "").strip()
    open_id = (me.get("openId") or "").strip()
    userid = ""
    if union_id:
        app_token = get_access_token(app_key, app_secret)
        userid = get_userid_by_unionid(app_token, union_id) or ""
    if not userid and me.get("mobile"):
        app_token = get_access_token(app_key, app_secret)
        from app.services.dingtalk.client import get_userid_by_mobile

        userid = get_userid_by_mobile(app_token, str(me.get("mobile"))) or ""
    if not userid:
        raise ValueError("未获取到钉钉 userid，请确认应用通讯录权限")
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise ValueError("用户不存在")
    user.dingtalk_userid = userid
    user.dingtalk_union_id = union_id or open_id or None
    user.dingtalk_bound_at = datetime.utcnow()
    db.flush()
    from app.services.dingtalk.welcome import send_bind_welcome

    send_bind_welcome(db, userid)
    return user


def get_user_by_dingtalk_userid(db: Session, userid: str) -> User | None:
    uid = (userid or "").strip()
    if not uid:
        return None
    return db.scalar(
        select(User).where(
            User.dingtalk_userid == uid,
            User.is_active.is_(True),
        )
    )
