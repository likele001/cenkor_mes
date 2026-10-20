# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""消息中心管理端接口：三通道总览、群组、规则、绑定、日志、预警接收人

配置的唯一存储仍是 tenant_settings 的 `feishu.notify`（v2 结构：groups[].channels 三通道嵌套），
这里只做跨通道的聚合视图。企微/钉钉通道由 notify_wecom_dingtalk 扩展提供发送实现，
总览接口动态检测扩展是否安装（_CHANNEL_TASK_MAP 注册）并读取真实配置。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.feishu_push_log import FeishuPushLog
from app.models.user import User
from app.services.feishu.settings import (
    EVENT_CATALOG,
    TARGET_OPTIONS,
    get_feishu_credentials,
    get_feishu_settings_raw,
    save_feishu_settings,
)
from app.services.feishu.urls import get_events_callback_url, get_oauth_redirect_uri
from app.services.notify_channels import KNOWN_EVENTS
from app.services.notify_migration import run_migration

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])

MAX_LOG_LIMIT = 200
ALERT_EVENT_CODE = "alert"


class GroupsIn(BaseModel):
    items: list[dict] = Field(default_factory=list)


class AlertRecipientsIn(BaseModel):
    user_ids: list[int] = Field(default_factory=list)


def _channel_config(raw: dict | None, *, kind: str) -> dict:
    raw = raw or {}
    out = {"enabled": bool(raw.get("enabled")), "chat_id": "", "webhook_url": "", "webhook_secret": ""}
    if kind == "feishu":
        out["chat_id"] = (raw.get("chat_id") or "").strip()
        out["webhook_url"] = (raw.get("webhook_url") or "").strip()
    else:
        out["webhook_url"] = (raw.get("webhook_url") or "").strip()
        out["webhook_secret"] = (raw.get("webhook_secret") or "").strip()
    # 只允许「填了地址才算启用」，避免前端留下开关开着但地址为空的死配置
    out["enabled"] = out["enabled"] and bool(out["chat_id"] or out["webhook_url"])
    return out


def _normalize_group(g: dict) -> dict:
    channels = g.get("channels") if isinstance(g.get("channels"), dict) else None
    if channels is None:
        channels = {
            "feishu": {"chat_id": g.get("chat_id") or "", "enabled": True},
            "wecom": {"webhook_url": g.get("webhook_url") or "", "enabled": True},
            "dingtalk": {},
        }
    code = (g.get("code") or "").strip()
    return {
        "code": code,
        "name": (g.get("name") or code).strip(),
        "enabled": bool(g.get("enabled", True)),
        "channels": {
            "feishu": _channel_config(channels.get("feishu"), kind="feishu"),
            "wecom": _channel_config(channels.get("wecom"), kind="wecom"),
            "dingtalk": _channel_config(channels.get("dingtalk"), kind="dingtalk"),
        },
    }


def _today_count(db: Session) -> int:
    today = datetime.utcnow().date()
    return int(
        db.scalar(
            select(func.count(FeishuPushLog.id)).where(func.date(FeishuPushLog.created_at) == today)
        )
        or 0
    )


def _disabled_channel() -> dict:
    return {
        "enabled": False,
        "configured": False,
        "agent_name": "",
        "agent_id": "",
        "today_total": 0,
        "callback_url": "",
        "oauth_redirect_url": "",
    }


def _extension_channel_overview(db: Session, channel: str) -> dict:
    """企微/钉钉通道总览（扩展安装后返回真实配置）。

    检测逻辑：
    1. 通道是否在 _CHANNEL_TASK_MAP 注册（扩展加载时调用 register_channel_task）
    2. 若注册，从 tenant_settings 读取 {channel}.notify 配置
    3. 若未注册，返回 _disabled_channel()
    """
    from app.services.notify_dispatcher import _CHANNEL_TASK_MAP

    if channel not in _CHANNEL_TASK_MAP:
        return _disabled_channel()

    # 扩展已安装，读取配置
    from app.crud.tenant_setting import get_setting

    cfg = get_setting(db, f"{channel}.notify") or {}
    enabled = bool(cfg.get("enabled"))
    # 企微: corp_id + agent_id + secret；钉钉: app_key + app_secret
    if channel == "wecom":
        configured = bool(cfg.get("corp_id") and cfg.get("secret"))
        agent_id = cfg.get("agent_id") or ""
        agent_name = "企微机器人"
    elif channel == "dingtalk":
        configured = bool(cfg.get("app_key") and cfg.get("app_secret"))
        agent_id = cfg.get("agent_id") or ""
        agent_name = "钉钉机器人"
    else:
        configured = False
        agent_id = ""
        agent_name = ""

    return {
        "enabled": enabled,
        "configured": configured,
        "agent_name": agent_name,
        "agent_id": agent_id,
        "today_total": 0,  # TODO: 按 channel 过滤 feishu_push_logs 统计
        "callback_url": "",
        "oauth_redirect_url": "",
    }


def _user_binding_out(u: User) -> dict:
    bound = any(
        (getattr(u, f) or "").strip()
        for f in ("feishu_open_id", "wecom_userid", "dingtalk_userid")
    )
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "phone": u.phone,
        "email": u.email,
        "department_id": u.department_id,
        "feishu_open_id": u.feishu_open_id,
        "feishu_bound_at": u.feishu_bound_at,
        "wecom_userid": u.wecom_userid,
        "wecom_bound_at": u.wecom_bound_at,
        "dingtalk_userid": u.dingtalk_userid,
        "dingtalk_bound_at": u.dingtalk_bound_at,
        "bound": bound,
    }


def _push_log_out(r: FeishuPushLog) -> dict:
    return {
        "id": r.id,
        "channel": "feishu",
        "event_code": r.event_code,
        "target_kind": r.target_kind,
        "target_ref": r.target_ref,
        "title": r.title,
        "content": r.content,
        "level": r.level,
        "biz_type": r.biz_type,
        "biz_id": r.biz_id,
        "status": r.status,
        "error_msg": r.error_msg,
        "message_id": r.feishu_message_id,
        "retry_count": r.retry_count,
        "alerted_at": r.alerted_at,
        "created_at": r.created_at,
        "sent_at": r.sent_at,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_feishu_settings_raw(db)
    app_id, secret = get_feishu_credentials(db)
    feishu = {
        "enabled": bool(cfg.get("enabled")),
        "configured": bool(app_id and secret),
        "agent_name": "CenkorMES 机器人",
        "agent_id": app_id or "",
        "today_total": _today_count(db),
        "callback_url": get_events_callback_url(cfg),
        "oauth_redirect_url": get_oauth_redirect_uri(cfg),
    }
    # 企微/钉钉：动态检测扩展是否安装
    wecom = _extension_channel_overview(db, "wecom")
    dingtalk = _extension_channel_overview(db, "dingtalk")
    return ok({"channels": {"feishu": feishu, "wecom": wecom, "dingtalk": dingtalk}})


@router.get("/groups")
def list_groups(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_feishu_settings_raw(db)
    return ok({"items": [_normalize_group(g) for g in (cfg.get("groups") or [])]})


@router.post("/groups")
def save_groups(
    payload: GroupsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = [_normalize_group(g) for g in payload.items]
    if not all(g["code"] for g in items):
        raise HTTPException(status_code=400, detail="群组编码不能为空")
    if len({g["code"] for g in items}) != len(items):
        raise HTTPException(status_code=400, detail="群组编码重复")
    saved = save_feishu_settings(db, {"groups": items})
    return ok({"items": [_normalize_group(g) for g in (saved.get("groups") or [])]})


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_feishu_settings_raw(db)
    rules = cfg.get("rules") or {}
    catalog = [e["code"] for e in EVENT_CATALOG]
    codes = catalog + [c for c in rules if c not in catalog]
    items = [
        {
            "event_code": code,
            "feishu_rule": rules.get(code) or {},
            "wecom_rule": {},
            "dingtalk_rule": {},
            # 规则存下来不等于会发：分发器只认注册过分类的事件码
            "dispatchable": code in KNOWN_EVENTS,
        }
        for code in codes
    ]
    return ok({
        "items": items,
        "event_catalog": EVENT_CATALOG,
        "target_options": TARGET_OPTIONS,
        "undispatchable": [code for code in codes if code not in KNOWN_EVENTS],
    })


@router.get("/user-bindings")
def user_bindings(
    keyword: str | None = Query(default=None, max_length=64),
    unbound_only: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(User).where(User.is_active.is_(True))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(User.username.like(like), User.full_name.like(like), User.phone.like(like), User.email.like(like))
        )
    if unbound_only:
        # 与 _user_binding_out 的 bound 语义对齐：任一通道有值即算已绑定
        stmt = stmt.where(
            and_(
                or_(User.feishu_open_id.is_(None), User.feishu_open_id == ""),
                or_(User.wecom_userid.is_(None), User.wecom_userid == ""),
                or_(User.dingtalk_userid.is_(None), User.dingtalk_userid == ""),
            )
        )
    rows = db.scalars(stmt.order_by(User.id).offset(offset).limit(limit)).all()
    return ok({"items": [_user_binding_out(u) for u in rows]})


@router.get("/push-logs")
def push_logs(
    channel: str | None = Query(default=None, max_length=16),
    event_code: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=16),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_LOG_LIMIT),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if channel in ("wecom", "dingtalk"):
        # 这两个通道还没有发送实现，也就没有日志表
        return ok({"items": []})
    stmt = select(FeishuPushLog).order_by(FeishuPushLog.id.desc())
    if event_code:
        stmt = stmt.where(FeishuPushLog.event_code == event_code)
    if status:
        stmt = stmt.where(FeishuPushLog.status == status)
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return ok({"items": [_push_log_out(r) for r in rows]})


def _alert_recipient_ids(cfg: dict) -> list[int]:
    rule = (cfg.get("rules") or {}).get(ALERT_EVENT_CODE) or {}
    ids: list[int] = []
    for code in rule.get("targets") or []:
        if isinstance(code, str) and code.startswith("user:"):
            try:
                ids.append(int(code.split(":", 1)[1]))
            except ValueError:
                continue
    return list(dict.fromkeys(ids))


@router.get("/alert-recipients")
def alert_recipients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_feishu_settings_raw(db)
    ids = _alert_recipient_ids(cfg)
    if not ids:
        return ok({"user_ids": [], "users": []})
    rows = db.scalars(select(User).where(User.id.in_(ids)).order_by(User.id)).all()
    return ok({
        "user_ids": ids,
        "users": [
            {"id": u.id, "username": u.username, "full_name": u.full_name, "is_superuser": u.is_superuser}
            for u in rows
        ],
    })


@router.put("/alert-recipients")
def save_alert_recipients(
    payload: AlertRecipientsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = get_feishu_settings_raw(db)
    rules = dict(cfg.get("rules") or {})
    rule = dict(rules.get(ALERT_EVENT_CODE) or {})
    # 保留 group:/permission: 等既有目标，只替换 user:<id> 这一段
    others = [c for c in (rule.get("targets") or []) if not str(c).startswith("user:")]
    ids = list(dict.fromkeys(payload.user_ids))
    rule["targets"] = others + [f"user:{uid}" for uid in ids]
    rules[ALERT_EVENT_CODE] = rule
    save_feishu_settings(db, {"rules": rules})
    return ok({"user_ids": ids})


@router.get("/all-bindable-users")
def all_bindable_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.id)).all()
    return ok({
        "items": [
            {"id": u.id, "username": u.username, "full_name": u.full_name, "is_superuser": u.is_superuser}
            for u in rows
        ]
    })


@router.post("/run-migration")
def migrate(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raw = run_migration(db)
    results = raw.get("result") or {}
    migrated = sum(1 for v in results.values() if str(v).startswith(("migrated", "patched")))
    return ok({
        "total_migrated": migrated,
        "skipped": len(results) - migrated,
        "detail": results,
    })
