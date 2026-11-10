# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""H5 消息通道绑定：飞书（核心免费）+ 企微/钉钉（付费扩展开关）"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.extension_host.state import runtime
from app.models.user import User
from app.services.feishu.oauth import get_bind_authorize_url
from app.services.feishu.settings import get_feishu_credentials, get_feishu_settings_raw
from app.services.feishu.urls import get_oauth_redirect_uri

router = APIRouter()

IM_EXT = "notify_wecom_dingtalk"


class ImBindIn(BaseModel):
    channel: str = Field(..., pattern="^(wecom|dingtalk)$")
    userid: str = Field(..., min_length=1, max_length=64)


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


@router.get("/feishu/bind-status")
def bind_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_feishu_settings_raw(db)
    app_id, secret = get_feishu_credentials(db)
    im_on = bool(runtime.is_enabled(IM_EXT))
    return ok({
        "feishu": {
            "free": True,
            "available": bool(app_id) and bool(secret) and bool(get_oauth_redirect_uri(cfg)),
            "enabled": bool(cfg.get("enabled")),
            "bound": bool(user.feishu_open_id),
            "bound_at": _fmt(user.feishu_bound_at),
            "bot_open_link": "",
        },
        "wecom": {
            "available": im_on,
            "bound": bool(user.wecom_userid),
            "userid": user.wecom_userid or "",
            "bound_at": _fmt(user.wecom_bound_at),
        },
        "dingtalk": {
            "available": im_on,
            "bound": bool(user.dingtalk_userid),
            "userid": user.dingtalk_userid or "",
            "bound_at": _fmt(user.dingtalk_bound_at),
        },
    })


@router.post("/feishu/bind-url")
def bind_url(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        url = get_bind_authorize_url(db, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ok({"authorize_url": url})


@router.post("/im/bind")
def im_bind(body: ImBindIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not runtime.is_enabled(IM_EXT):
        raise HTTPException(403, "「企微/钉钉通知」扩展未开通，请先在应用市场的扩展应用中开通后再绑定。")
    userid = body.userid.strip()
    if body.channel == "wecom":
        user.wecom_userid = userid
        user.wecom_bound_at = datetime.utcnow()
    else:
        user.dingtalk_userid = userid
        user.dingtalk_bound_at = datetime.utcnow()
    db.commit()
    return ok({"bound": True, "channel": body.channel, "userid": userid})
