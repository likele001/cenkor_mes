# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""飞书推送管理端接口：配置、绑定、群/部门、日志、诊断、模拟与卡片预览"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.department import Department
from app.models.feishu_push_log import FeishuPushLog
from app.models.user import User
from app.services.feishu.cards import build_card
from app.services.feishu.client import (
    FeishuApiError,
    batch_get_user_id_by_mobiles,
    get_tenant_access_token,
    list_bot_chats,
    list_departments,
    send_interactive_message,
    send_text_message,
)
from app.services.feishu.delivery import build_delivery_diagnostics
from app.services.feishu.notify import enqueue_feishu_push
from app.services.feishu.oauth import get_bind_authorize_url
from app.services.feishu.settings import (
    get_feishu_credentials,
    get_feishu_settings_admin,
    get_feishu_settings_raw,
    save_feishu_settings,
)
from app.services.feishu.setup_check import build_personal_push_setup_check
from app.services.feishu.targets import resolve_targets
from app.services.feishu.urls import get_events_callback_url

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])

MAX_PUSH_LOG_LIMIT = 200


class SettingsIn(BaseModel):
    model_config = {"extra": "allow"}


class TestSendIn(BaseModel):
    receive_id: str = Field(min_length=1, max_length=128)
    receive_id_type: str = Field(default="open_id", pattern="^(open_id|user_id|union_id|chat_id|email)$")
    text: str | None = Field(default=None, max_length=2000)


class UserBindingIn(BaseModel):
    feishu_open_id: str | None = Field(default=None, max_length=64)
    feishu_user_id: str | None = Field(default=None, max_length=64)


class DeptBindingIn(BaseModel):
    feishu_open_department_id: str | None = Field(default=None, max_length=64)
    feishu_chat_group_code: str | None = Field(default=None, max_length=32)


class SimulateIn(BaseModel):
    event_code: str = Field(min_length=1, max_length=64)
    user_id: int | None = None
    department_id: int | None = None
    workshop: str | None = Field(default=None, max_length=64)


class BindUrlIn(BaseModel):
    user_id: int | None = None


class PreviewCardIn(BaseModel):
    event_code: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=128)
    content: str | None = Field(default=None, max_length=2000)
    level: str | None = Field(default=None, max_length=16)
    biz_type: str | None = Field(default=None, max_length=32)
    biz_id: int | None = None


def _require_credentials(db: Session) -> tuple[str, str]:
    app_id, secret = get_feishu_credentials(db)
    if not app_id or not secret:
        raise HTTPException(status_code=400, detail="请先填写并保存 App ID 与 App Secret")
    return app_id, secret


def _guard_feishu_error(fn):
    """飞书开放平台异常统一转 400，让管理端能看到具体原因而不是 500。"""
    try:
        return fn()
    except FeishuApiError as e:
        raise HTTPException(status_code=400, detail=f"飞书接口错误：{e.msg}") from e


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "phone": u.phone,
        "email": u.email,
        "department_id": u.department_id,
        "feishu_open_id": u.feishu_open_id,
        "feishu_user_id": u.feishu_user_id,
        "feishu_bound_at": u.feishu_bound_at,
        "bound": bool((u.feishu_open_id or "").strip()),
    }


def _log_out(r: FeishuPushLog) -> dict:
    return {
        "id": r.id,
        "event_code": r.event_code,
        "target_kind": r.target_kind,
        "target_ref": r.target_ref,
        "title": r.title,
        "content": r.content,
        "level": r.level,
        "status": r.status,
        "error_msg": r.error_msg,
        "feishu_message_id": r.feishu_message_id,
        "created_at": r.created_at,
        "sent_at": r.sent_at,
    }


@router.get("/feishu")
def read_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_feishu_settings_admin(db))


@router.put("/feishu")
def write_settings(
    payload: SettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok(save_feishu_settings(db, payload.model_dump()))


@router.post("/feishu/test-connection")
def test_connection(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app_id, secret = _require_credentials(db)
    token = _guard_feishu_error(lambda: get_tenant_access_token(app_id, secret, force_refresh=True))
    return ok({"ok": True, "token_preview": f"{token[:6]}…{token[-4:]}" if len(token) > 12 else "***"})


@router.post("/feishu/test-send")
def test_send(
    payload: TestSendIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app_id, secret = _require_credentials(db)
    cfg = get_feishu_settings_raw(db)

    def _send():
        token = get_tenant_access_token(app_id, secret)
        text = (payload.text or "").strip() or "【CenkorMES】飞书推送连通性测试"
        if (cfg.get("message_format") or "card") == "card":
            card = build_card(
                title="连通性测试",
                content=text,
                level="info",
                event_code="alert",
                target_kind="chat" if payload.receive_id_type == "chat_id" else "user",
            )
            return send_interactive_message(
                access_token=token,
                receive_id=payload.receive_id,
                receive_id_type=payload.receive_id_type,
                card=card,
            )
        return send_text_message(
            access_token=token,
            receive_id=payload.receive_id,
            receive_id_type=payload.receive_id_type,
            text=text,
        )

    message_id = _guard_feishu_error(_send)

    delivery: dict[str, Any] | None = None
    if payload.receive_id_type != "chat_id":
        delivery = _guard_feishu_error(
            lambda: build_delivery_diagnostics(
                app_id=app_id,
                app_secret=secret,
                feishu_open_id=payload.receive_id,
                latest_message_id=message_id,
            )
        )
    return ok({"ok": True, "message_id": message_id, "delivery": delivery})


@router.get("/feishu/delivery-diagnostics")
def delivery_diagnostics(
    user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app_id, secret = _require_credentials(db)
    target = db.get(User, user_id) if user_id else user
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    open_id = (target.feishu_open_id or "").strip()
    if not open_id:
        raise HTTPException(status_code=400, detail="该用户尚未绑定飞书 open_id")
    latest = db.scalar(
        select(FeishuPushLog.feishu_message_id)
        .where(
            FeishuPushLog.target_kind == "user",
            FeishuPushLog.target_ref == open_id,
            FeishuPushLog.feishu_message_id.isnot(None),
        )
        .order_by(FeishuPushLog.id.desc())
    )
    data = _guard_feishu_error(
        lambda: build_delivery_diagnostics(
            app_id=app_id,
            app_secret=secret,
            feishu_open_id=open_id,
            latest_message_id=latest,
        )
    )
    return ok(data)


@router.get("/feishu/setup-checklist")
def setup_checklist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app_id, secret = _require_credentials(db)
    cfg = get_feishu_settings_raw(db)
    data = _guard_feishu_error(
        lambda: build_personal_push_setup_check(
            app_id=app_id,
            app_secret=secret,
            callback_url=get_events_callback_url(cfg),
        )
    )
    return ok(data)


@router.get("/feishu/chats")
def bot_chats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app_id, secret = _require_credentials(db)
    items = _guard_feishu_error(lambda: list_bot_chats(get_tenant_access_token(app_id, secret)))
    return ok({"items": items})


@router.get("/feishu/feishu-departments")
def feishu_departments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app_id, secret = _require_credentials(db)
    rows = _guard_feishu_error(lambda: list_departments(get_tenant_access_token(app_id, secret)))
    return ok({"items": rows})


@router.get("/feishu/push-logs")
def push_logs(
    event_code: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=16),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PUSH_LOG_LIMIT),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(FeishuPushLog).order_by(FeishuPushLog.id.desc())
    if event_code:
        stmt = stmt.where(FeishuPushLog.event_code == event_code)
    if status:
        stmt = stmt.where(FeishuPushLog.status == status)
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return ok({"items": [_log_out(r) for r in rows]})


@router.post("/feishu/push-logs/{log_id}/retry")
def retry_push_log(
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(FeishuPushLog, log_id)
    if not row:
        raise HTTPException(status_code=404, detail="推送记录不存在")
    row.status = "pending"
    row.error_msg = None
    row.retry_count = (row.retry_count or 0) + 1
    db.flush()
    enqueue_feishu_push(db, row.id)
    return ok({"id": row.id, "status": row.status})


@router.get("/feishu/user-bindings")
def user_bindings(
    keyword: str | None = Query(default=None, max_length=64),
    unbound_only: bool = Query(default=False),
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
        stmt = stmt.where(or_(User.feishu_open_id.is_(None), User.feishu_open_id == ""))
    rows = db.scalars(stmt.order_by(User.id)).all()
    return ok({"items": [_user_out(u) for u in rows]})


@router.put("/feishu/user-bindings/{target_user_id}")
def update_user_binding(
    target_user_id: int,
    payload: UserBindingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    open_id = (payload.feishu_open_id or "").strip() or None
    target.feishu_open_id = open_id
    target.feishu_user_id = (payload.feishu_user_id or "").strip() or None
    target.feishu_bound_at = datetime.utcnow() if open_id else None
    db.flush()
    return ok(_user_out(target))


@router.post("/feishu/user-bindings/batch-match-mobile")
def batch_match_mobile(
    refresh_all: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app_id, secret = _require_credentials(db)
    stmt = select(User).where(User.is_active.is_(True), User.phone.isnot(None), User.phone != "")
    if not refresh_all:
        stmt = stmt.where(or_(User.feishu_open_id.is_(None), User.feishu_open_id == ""))
    candidates = db.scalars(stmt.order_by(User.id)).all()
    if not candidates:
        return ok({"matched": 0, "total": 0})

    by_mobile: dict[str, list[User]] = {}
    for u in candidates:
        by_mobile.setdefault((u.phone or "").strip(), []).append(u)
    mobiles = list(by_mobile.keys())

    matched = 0
    for start in range(0, len(mobiles), 50):
        chunk = mobiles[start : start + 50]
        rows = _guard_feishu_error(lambda: batch_get_user_id_by_mobiles(get_tenant_access_token(app_id, secret), chunk))
        for item in rows:
            oid = (item.get("open_id") or item.get("user_id") or "").strip()
            if not oid:
                continue
            for u in by_mobile.get((item.get("mobile") or "").strip(), []):
                u.feishu_open_id = oid
                u.feishu_bound_at = datetime.utcnow()
                matched += 1
    db.flush()
    return ok({"matched": matched, "total": len(mobiles), "refreshed": refresh_all})


@router.get("/feishu/department-bindings")
def department_bindings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Department).order_by(Department.id)).all()
    return ok({
        "items": [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "parent_id": d.parent_id,
                "feishu_open_department_id": d.feishu_open_department_id,
                "feishu_chat_group_code": d.feishu_chat_group_code,
            }
            for d in rows
        ]
    })


@router.put("/feishu/department-bindings/{department_id}")
def update_department_binding(
    department_id: int,
    payload: DeptBindingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dept = db.get(Department, department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    dept.feishu_open_department_id = (payload.feishu_open_department_id or "").strip() or None
    dept.feishu_chat_group_code = (payload.feishu_chat_group_code or "").strip() or None
    db.flush()
    return ok({
        "id": dept.id,
        "code": dept.code,
        "name": dept.name,
        "parent_id": dept.parent_id,
        "feishu_open_department_id": dept.feishu_open_department_id,
        "feishu_chat_group_code": dept.feishu_chat_group_code,
    })


def _describe_targets(db: Session, cfg: dict, targets: list[dict]) -> list[dict]:
    """把解析结果翻成人能核对的样子。

    模拟器给的是配规则的人看的，只回 ou_xxx / oc_xxx 他没法判断到底命中了谁。
    """
    group_names = {str(g.get("code")): (g.get("name") or "") for g in cfg.get("groups") or []}
    out: list[dict] = []
    for t in targets:
        row: dict[str, Any] = {"kind": t["kind"], "ref": t["ref"]}
        if t["kind"] == "user":
            target = db.get(User, int(t["user_id"])) if t.get("user_id") else None
            row["name"] = (target.full_name or target.username) if target else None
            row["username"] = target.username if target else None
        else:
            code = t.get("chat_code") or ""
            row["chat_code"] = code
            row["name"] = "部门自动群" if code == "dept_auto" else (group_names.get(code) or None)
        out.append(row)
    return out


def _simulate_targets(db: Session, cfg: dict, codes: list[str], scope: dict) -> dict:
    """整体 + 逐条目标码各解析一遍：逐条才看得出哪一行目标什么都没命中。"""
    resolved = {code: _describe_targets(db, cfg, resolve_targets(db, [code], **scope)) for code in codes}
    return {
        "targets": _describe_targets(db, cfg, resolve_targets(db, codes, **scope)),
        "by_code": resolved,
        "unresolved": [code for code, rows in resolved.items() if not rows],
    }


@router.post("/feishu/simulate")
def simulate(
    payload: SimulateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = get_feishu_settings_raw(db)
    rule = (cfg.get("rules") or {}).get(payload.event_code)
    if rule is None and payload.event_code.startswith("alert"):
        rule = (cfg.get("rules") or {}).get("alert")
    if rule is None:
        raise HTTPException(status_code=404, detail="该事件没有推送规则")
    scope = {
        "user_id": payload.user_id,
        "department_id": payload.department_id,
        "workshop": payload.workshop,
    }
    escalation = {
        level: _describe_targets(db, cfg, resolve_targets(db, codes, **scope))
        for level, codes in (rule.get("escalation") or {}).items()
    }
    return ok({
        **_simulate_targets(db, cfg, list(rule.get("targets") or []), scope),
        "escalation": escalation,
        "enabled": bool(rule.get("enabled", True)),
        "rule": rule,
    })


@router.post("/feishu/bind-url")
def bind_url(
    payload: BindUrlIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target_id = payload.user_id or user.id
    target = db.get(User, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        url = get_bind_authorize_url(db, target_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ok({"authorize_url": url, "user_id": target_id})


@router.post("/feishu/preview-card")
def preview_card(
    payload: PreviewCardIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event_code = payload.event_code or "alert"
    card = build_card(
        title=(payload.title or "").strip() or "示例通知标题",
        content=(payload.content or "").strip() or "这是一条卡片内容预览，实际推送会带上事件对应的时间与业务信息。",
        level=payload.level or "info",
        event_code=event_code,
        biz_type=payload.biz_type,
        biz_id=payload.biz_id,
    )
    return ok({"card": card})
