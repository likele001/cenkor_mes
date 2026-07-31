"""推送连续失败告警 + 告警接收人

按事件 + 通道 维度统计连续失败次数，达到阈值通知管理员。
告警接收人从 tenant_settings `notify_guard.recipients` 读取；
为空时回退到全部 superuser + admin 角色。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting
from app.models.dingtalk_push_log import DingtalkPushLog
from app.models.feishu_push_log import FeishuPushLog
from app.models.role import Role
from app.models.user import User, user_roles
from app.models.wecom_push_log import WecomPushLog

logger = logging.getLogger(__name__)

ALERT_THRESHOLD = 5
ALERT_DEDUP_MINUTES = 60
RECIPIENTS_KEY = "notify_guard.recipients"
ALERT_HISTORY_KEY = "notify_guard.history"


def get_recipients(db: Session) -> list[int]:
    """读取告警接收人 user_id 列表，为空时回退到所有超管 + admin 角色"""
    row = get_setting(db, RECIPIENTS_KEY)
    if row and row.value:
        try:
            ids = json.loads(row.value)
            if isinstance(ids, list) and all(isinstance(x, int) for x in ids):
                return [int(x) for x in ids]
        except Exception:
            pass

    admin_role_user_ids = db.execute(
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.code == "admin")
    ).scalars().all()
    superuser_ids = db.execute(
        select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
    ).scalars().all()

    return sorted(set(list(admin_role_user_ids) + list(superuser_ids)))


def save_recipients(db: Session, user_ids: list[int]) -> None:
    upsert_setting(db, key=RECIPIENTS_KEY, value=json.dumps([int(x) for x in user_ids]))


def _dedup_check(db: Session, event_code: str, channel: str) -> bool:
    row = get_setting(db, ALERT_HISTORY_KEY)
    if not row or not row.value:
        return False
    try:
        history = json.loads(row.value)
    except Exception:
        return False
    key = f"{channel}:{event_code}"
    last = history.get(key)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    return datetime.utcnow() - last_dt < timedelta(minutes=ALERT_DEDUP_MINUTES)


def _record_alert(db: Session, event_code: str, channel: str) -> None:
    row = get_setting(db, ALERT_HISTORY_KEY)
    history = {}
    if row and row.value:
        try:
            history = json.loads(row.value)
        except Exception:
            history = {}
    history[f"{channel}:{event_code}"] = datetime.utcnow().isoformat()
    cutoff = datetime.utcnow() - timedelta(days=7)
    history = {k: v for k, v in history.items() if (lambda dt: dt >= cutoff)(datetime.fromisoformat(v) if v else cutoff)}
    upsert_setting(db, key=ALERT_HISTORY_KEY, value=json.dumps(history, ensure_ascii=False))


def _send_in_app_alerts(db: Session, user_ids: list[int], title: str, content: str) -> None:
    from app.crud.notification import create_notification

    for uid in user_ids:
        try:
            create_notification(
                db,
                user_id=uid,
                title=title,
                content=content,
                level="error",
                biz_type="notify_guard",
                biz_id=0,
            )
        except Exception as e:
            logger.warning("notify_guard in_app alert failed uid=%s: %s", uid, e)


def check_consecutive_failures(db: Session, event_code: str, channel: str) -> None:
    """Celery 任务失败时调用：检查该事件+该通道最近是否连续失败

    当任一通道的同一事件最近 ALERT_THRESHOLD 条全部失败时触发告警
    """
    if _dedup_check(db, event_code, channel):
        return

    model_map = {
        "feishu": FeishuPushLog,
        "wecom": WecomPushLog,
        "dingtalk": DingtalkPushLog,
    }
    model = model_map.get(channel)
    if not model:
        return
    recent = db.execute(
        select(model)
        .where(model.event_code == event_code)
        .order_by(desc(model.id))
        .limit(ALERT_THRESHOLD)
    ).scalars().all()

    if len(recent) < ALERT_THRESHOLD:
        return
    if not all(r.status == "failed" for r in recent):
        return

    for r in recent:
        r.alerted_at = datetime.utcnow()

    recipients = get_recipients(db)
    if not recipients:
        logger.warning("notify_guard: no recipients for event %s", event_code)
        return

    title = "推送异常"
    content = f"事件 {event_code} 在 {channel} 通道连续失败 {ALERT_THRESHOLD} 次，请检查通道配置。"
    _send_in_app_alerts(db, recipients, title, content)
    _record_alert(db, event_code, channel)

    try:
        from app.services.notify_dispatcher import dispatch as notify_dispatch

        notify_dispatch(
            db,
            "alert",
            title=title,
            content=content,
            level="danger",
            biz_type="notify_guard",
            biz_id=0,
        )
    except Exception as e:
        logger.warning("notify_guard group dispatch failed: %s", e)
