"""钉钉消息推送分发"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.dingtalk_push_log import DingtalkPushLog

logger = logging.getLogger(__name__)


def enqueue_dingtalk_push(db: Session, log_id: int) -> None:
    """等事务 commit 后再 enqueue，避免 worker 查到 log_not_found。"""
    from app.services.notify_dispatcher import enqueue_after_commit

    enqueue_after_commit(db, "dingtalk", log_id)


def emit_dingtalk_event(
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
    payload: dict | None = None,
) -> int:
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
        # 钉钉入口：限制只产钉钉通道的 log，避免与飞书/企微 emit 重叠
        restrict_channel="dingtalk",
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
    from app.models.user import User
    from app.services.dingtalk.targets import get_user_department_and_workshop

    report_user = db.get(User, report_user_id)
    tenant_id = report_user.tenant_id if report_user else 1
    dept_id, workshop = get_user_department_and_workshop(db, tenant_id, report_user_id, process_id)
    # 站内通知由统一分发器（dispatcher 规则分支）创建一次，避免三通道 emit 重复产生多条

    emit_dingtalk_event(
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
    from app.services.dingtalk.settings import get_dingtalk_settings_raw

    cfg = get_dingtalk_settings_raw(db)
    rule = (cfg.get("rules") or {}).get("dispatch.assigned") or {}
    channels = rule.get("channels") or ["dingtalk", "in_app"]

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
        emit_dingtalk_event(
            db,
            "dispatch.assigned",
            title=title,
            content=content,
            level="info",
            biz_type=biz_type,
            biz_id=biz_id,
            user_id=uid,
            payload={"task_code": task_code} if task_code else None,
        )


def mark_push_log_result(
    db: Session,
    log_id: int,
    *,
    success: bool,
    task_id: str | None = None,
    error_msg: str | None = None,
) -> None:
    row = db.get(DingtalkPushLog, log_id)
    if not row:
        return
    row.status = "success" if success else "failed"
    row.dingtalk_task_id = task_id
    row.error_msg = (error_msg or "")[:500] or None
    row.sent_at = datetime.utcnow()
    if not success:
        row.retry_count = int(row.retry_count or 0) + 1
    db.flush()


def flush_deferred_messages(db: Session) -> int:
    from sqlalchemy import select

    now = datetime.utcnow()
    rows = db.scalars(
        select(DingtalkPushLog).where(
            DingtalkPushLog.status == "deferred",
            DingtalkPushLog.scheduled_at.isnot(None),
            DingtalkPushLog.scheduled_at <= now,
        )
    ).all()
    n = 0
    for row in rows:
        row.status = "pending"
        enqueue_dingtalk_push(db, row.id)
        n += 1
    return n
