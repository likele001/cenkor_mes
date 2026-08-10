"""飞书 OAuth 绑定用户 open_id"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.services.feishu.client import FeishuApiError, get_tenant_access_token
from app.services.feishu.settings import get_feishu_credentials, get_feishu_settings_raw
from app.services.feishu.urls import get_oauth_redirect_uri

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


def create_bind_state(*, user_id: int, minutes: int = 30) -> str:
    return create_access_token(
        {"purpose": "feishu_bind", "sub": str(user_id)},
        expires_minutes=minutes,
    )


def parse_bind_state(state: str) -> int:
    data = decode_token(state)
    if data.get("purpose") != "feishu_bind":
        raise ValueError("invalid bind state")
    return int(data["sub"])


def build_authorize_url(*, app_id: str, redirect_uri: str, state: str) -> str:
    return (
        "https://open.feishu.cn/open-apis/authen/v1/authorize"
        f"?app_id={quote(app_id)}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&state={quote(state)}"
    )


def exchange_code_for_user_info(app_id: str, app_secret: str, code: str) -> dict:
    app_token = get_tenant_access_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{FEISHU_API_BASE}/authen/v1/oidc/access_token",
            headers=headers,
            json={"grant_type": "authorization_code", "code": code},
        )
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        raise FeishuApiError(int(data.get("code", -1)), str(data.get("msg") or "oidc token failed"))
    access_token = (data.get("data") or {}).get("access_token")
    if not access_token:
        raise FeishuApiError(-1, "empty user access_token")
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/authen/v1/user_info",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        udata = resp.json()
    if int(udata.get("code", -1)) != 0:
        raise FeishuApiError(int(udata.get("code", -1)), str(udata.get("msg") or "user_info failed"))
    return udata.get("data") or {}


def bind_user_with_code(db: Session, *, user_id: int, code: str) -> User:
    app_id, secret = get_feishu_credentials(db)
    if not app_id or not secret:
        raise ValueError("飞书应用未配置")
    info = exchange_code_for_user_info(app_id, secret, code)
    open_id = (info.get("open_id") or info.get("openId") or "").strip()
    if not open_id:
        raise ValueError("未获取到飞书 open_id")
    user = db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    user.feishu_open_id = open_id
    user.feishu_user_id = (info.get("user_id") or info.get("userId") or user.feishu_user_id or None)
    user.feishu_union_id = (info.get("union_id") or info.get("unionId") or user.feishu_union_id or None)
    user.feishu_bound_at = datetime.utcnow()
    db.flush()
    from app.services.feishu.welcome import send_bind_welcome

    send_bind_welcome(db, open_id)
    return user


def get_bind_authorize_url(db: Session, user_id: int) -> str:
    cfg = get_feishu_settings_raw(db)
    app_id, _ = get_feishu_credentials(db)
    redirect_uri = get_oauth_redirect_uri(cfg)
    if not app_id or not redirect_uri:
        raise ValueError("请先配置 App ID 与 PUBLIC_BASE_URL（API 外网地址）")
    state = create_bind_state(user_id=user_id)
    return build_authorize_url(app_id=app_id, redirect_uri=redirect_uri, state=state)


def get_user_by_feishu_open_id(db: Session, open_id: str) -> User | None:
    oid = (open_id or "").strip()
    if not oid:
        return None
    return db.scalar(
        select(User).where(
            User.feishu_open_id == oid,
            User.is_active.is_(True),
        )
    )
