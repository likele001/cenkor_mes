# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""微信小程序订阅消息路由

补齐小程序端一直 404 的两个接口：
  GET  /miniapp/wechat-mp/templates          可订阅模板列表
  GET  /miniapp/wechat-mp/my-subscriptions   当前用户已订阅记录
  POST /miniapp/wechat-mp/subscribe          记录一次订阅结果

模板配置存放在 platform_settings，key = wechat_mp_templates，值为 JSON 数组：
  [{"event_code":"task_assigned","template_id":"...","title":"任务派发",
    "content":"...","keywords":["thing1","time2"]}]

未配置时返回空列表（前端显示「暂无可用模板」），不再 404。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models.platform_setting import PlatformSetting
from app.models.user import User
from app.models.user_wechat_subscription import UserWechatSubscription

router = APIRouter()

TEMPLATES_KEY = "wechat_mp_templates"


def _load_templates(db: Session) -> list[dict]:
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == TEMPLATES_KEY))
    if not row or not row.value:
        return []
    try:
        data = json.loads(row.value)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for t in data:
        if not isinstance(t, dict):
            continue
        # 过滤掉占位模板（未在微信公众平台配置真实 template_id 的项）
        tid = (t.get("template_id") or "").strip()
        if not tid or tid.startswith("tpl_"):
            continue
        out.append(
            {
                "event_code": t.get("event_code") or "",
                "template_id": tid,
                "title": t.get("title") or "",
                "content": t.get("content") or "",
                "keywords": t.get("keywords") or [],
            }
        )
    return out


@router.get("/templates")
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """可订阅模板列表（前端用于 uni.requestSubscribeMessage 的 tmplIds）"""
    return ok({"items": _load_templates(db)})


@router.get("/my-subscriptions")
def my_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户的订阅记录，按接受次数倒序"""
    rows = db.scalars(
        select(UserWechatSubscription)
        .where(UserWechatSubscription.user_id == user.id)
        .order_by(UserWechatSubscription.accept_count.desc(), UserWechatSubscription.id.desc())
    ).all()
    return ok(
        {
            "items": [
                {
                    "event_code": r.event_code,
                    "template_id": r.template_id,
                    "accept_count": r.accept_count,
                    "reject_count": r.reject_count,
                    "last_accepted_at": r.last_accepted_at,
                    "last_rejected_at": r.last_rejected_at,
                }
                for r in rows
            ]
        }
    )


class SubscribeIn(BaseModel):
    event_code: str
    template_id: str
    accepted: bool = True


@router.post("/subscribe")
def record_subscribe(
    payload: SubscribeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """记录一次订阅结果（前端调用 uni.requestSubscribeMessage 成功后回写）

    同一 (user, event_code, template_id) 只保留一条，累加计数。
    """
    from datetime import datetime

    row = db.scalar(
        select(UserWechatSubscription).where(
            UserWechatSubscription.user_id == user.id,
            UserWechatSubscription.event_code == payload.event_code,
            UserWechatSubscription.template_id == payload.template_id,
        )
    )
    now = datetime.now()
    if row is None:
        row = UserWechatSubscription(
            tenant_id=user.tenant_id or 1,
            user_id=user.id,
            event_code=payload.event_code,
            template_id=payload.template_id,
            accept_count=1 if payload.accepted else 0,
            reject_count=0 if payload.accepted else 1,
            last_accepted_at=now if payload.accepted else None,
            last_rejected_at=None if payload.accepted else now,
        )
        db.add(row)
    else:
        if payload.accepted:
            row.accept_count = (row.accept_count or 0) + 1
            row.last_accepted_at = now
        else:
            row.reject_count = (row.reject_count or 0) + 1
            row.last_rejected_at = now
    db.commit()
    return ok({"ok": True})
