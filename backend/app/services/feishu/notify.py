"""飞书消息推送分发"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.feishu_push_log import FeishuPushLog
from app.services.feishu.links import build_message_urls
from app.services.feishu.quiet_hours import is_in_quiet_hours, next_send_time
from app.services.feishu.settings import get_feishu_settings_raw, is_feishu_enabled
from app.services.feishu.targets import notify_in_app_for_targets, resolve_alert_targets, resolve_targets

logger = logging.getLogger(__name__)


def _rule_for_event(cfg: dict, event_code: str) -> dict | None:
    rules = cfg.get("rules") or {}
    if event_code in rules:
        return rules[event_code]
    if event_code.startswith("alert") and "alert" in rules:
        return rules["alert"]
    return None


def _build_payload(
    cfg: dict,
    *,
    event_code: str,
    title: str,
    content: str,
    level: str,
    biz_type: str | None,
    biz_id: int | None,
    target_kind: str,
) -> dict:
    h5_url, admin_url = build_message_urls(cfg, event_code=event_code, biz_type=biz_type, biz_id=biz_id)
    include_audit = bool(cfg.get("card_actions_enabled", True)) and event_code == "report.submitted"
    return {
        "event_code": event_code,
        "title": title,
        "content": content,
        "level": level,
        "biz_type": biz_type,
        "biz_id": biz_id,
        "target_kind": target_kind,
        "message_format": cfg.get("message_format") or "card",
        "h5_url": h5_url,
        "admin_url": admin_url,
        "include_audit_actions": include_audit,
    }


def _create_push_log(
    db: Session,
    *,
    event_code: str,
    target: dict,
    title: str,
    content: str,
    level: str,
    biz_type: str | None,
    biz_id: int | None,
    payload: dict | None = None,
    scheduled_at: datetime | None = None,
) -> FeishuPushLog:
    row = FeishuPushLog(
        tenant_id=1,
        event_code=event_code,
        target_kind=target["kind"],
        target_ref=target["ref"],
        title=title[:128],
        content=content,
        level=level,
        biz_type=biz_type,
        biz_id=biz_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        scheduled_at=scheduled_at,
        status="deferred" if scheduled_at and scheduled_at > datetime.now() else "pending",
    )
    db.add(row)
    db.flush()
    return row


def enqueue_feishu_push(db: Session, log_id: int) -> None:
    """等事务 commit 后再 enqueue，避免 worker 查到 log_not_found。"""
    from app.services.notify_dispatcher import enqueue_after_commit

    enqueue_after_commit(db, "feishu", log_id)


def emit_feishu_event(
    db: Session,
    event_code: str,
    *,
    title: str,
    content: str,
    level: str = "info",
    biz_type: str | None = None,
    biz_id: int | None = None,
    user_id: int | None = None,
    department_id: int | None = None,
    workshop: str | None = None,
    scheduled_at: datetime | None = None,
    payload: dict | None = None,
) -> int:
    """兼容旧调用：转发到统一 dispatcher，由 dispatcher 决定飞书/企微通道分发"""
    from app.services.notify_dispatcher import dispatch as _dispatch

    return _dispatch(
        db,
        event_code,
        title=title,
        content=content,
        level=level,
        biz_type=biz_type,
        biz_id=biz_id,
        user_id=user_id,
        department_id=department_id,
        workshop=workshop,
        scheduled_at=scheduled_at,
        # 飞书入口：限制只产飞书通道的 log，避免与企微/钉钉 emit 重叠
        restrict_channel="feishu",
        payload=payload,
    )


def notify_report_submitted(
    db: Session,
    *,
    report_user_id: int,
    process_id: int | None,
    title: str,
    content: str,
    biz_type: str,
    biz_id: int,
) -> None:
    from app.services.feishu.targets import get_user_department_and_workshop

    dept_id, workshop = get_user_department_and_workshop(db, report_user_id, process_id)
    # 站内通知由统一分发器（dispatcher 规则分支）创建一次，避免三通道 emit 重复产生多条

    emit_feishu_event(
        db,
        "report.submitted",
        title=title,
        content=content,
        level="warning",
        biz_type=biz_type,
        biz_id=biz_id,
        user_id=report_user_id,
        department_id=dept_id,
        workshop=workshop,
    )


def notify_dispatch_assigned(
    db: Session,
    *,
    user_ids: list[int],
    title: str,
    content: str,
    biz_type: str = "task",
    biz_id: int | None = None,
    task_code: str | None = None,
) -> None:
    from app.crud.notification import create_notification

    cfg = get_feishu_settings_raw(db)
    rule = _rule_for_event(cfg, "dispatch.assigned") or {}
    channels = rule.get("channels") or ["feishu", "in_app"]

    for uid in user_ids:
        if "in_app" in channels:
            create_notification(
                db,
                user_id=uid,
                title=title,
                content=content,
                level="info",
                biz_type=biz_type,
                biz_id=biz_id,
            )
        emit_feishu_event(
            db,
            "dispatch.assigned",
            title=title,
            content=content,
            level="info",
            biz_type=biz_type,
            biz_id=biz_id,
            user_id=uid,
            # 透传 task_code，飞书卡片 build_card 会读它拼「立即报工」深链
            payload={"task_code": task_code} if task_code else None,
        )


def mark_push_log_result(
    db: Session,
    log_id: int,
    *,
    success: bool,
    message_id: str | None = None,
    error_msg: str | None = None,
) -> None:
    row = db.get(FeishuPushLog, log_id)
    if not row:
        return
    row.status = "success" if success else "failed"
    row.feishu_message_id = message_id
    row.error_msg = (error_msg or "")[:500] or None
    row.sent_at = datetime.utcnow()
    db.flush()


def flush_deferred_messages(db: Session) -> int:
    from sqlalchemy import select

    now = datetime.utcnow()
    rows = db.scalars(
        select(FeishuPushLog).where(
            FeishuPushLog.status == "deferred",
            FeishuPushLog.scheduled_at.isnot(None),
            FeishuPushLog.scheduled_at <= now,
        )
    ).all()
    n = 0
    for row in rows:
        row.status = "pending"
        enqueue_feishu_push(db, row.id)
        n += 1
    return n
