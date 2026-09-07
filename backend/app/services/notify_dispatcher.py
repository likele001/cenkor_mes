# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""统一消息分发器

根据事件类型 + 用户绑定情况，路由到飞书（开源版仅保留飞书单渠道）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.feishu_push_log import FeishuPushLog
from app.models.user import User
from app.services.feishu.settings import get_feishu_settings_raw, is_feishu_enabled
from app.services.notify_channels import (
    EVENT_GROUP_CODES,
    PushTarget,
    is_group_only_event,
    is_mixed_event,
    is_personal_event,
    is_rule_based_event,
)

logger = logging.getLogger(__name__)


# 通道 -> celery 任务名映射（仅飞书）
_CHANNEL_TASK_MAP: dict[str, str] = {
    "feishu": "feishu.send_message",
}


def _do_send_task(channel: str, log_id: int) -> None:
    """实际发送 celery 任务（不涉及事务）。"""
    task_name = _CHANNEL_TASK_MAP.get(channel)
    if not task_name:
        return
    try:
        from app.celery_app import celery

        celery.send_task(task_name, args=[int(log_id)])
    except Exception as e:
        logger.warning("enqueue %s push failed log_id=%s: %s", channel, log_id, e)


def enqueue_after_commit(db: Session, channel: str, log_id: int) -> None:
    """等当前事务 commit 后再 enqueue 推送任务。

    必要性：业务事件 emit 时 push_log 只 flush 未 commit，若立刻把
    celery 任务丢给 worker，worker 用新 session 查不到该 log，会返回
    `log_not_found`，导致 push_log 永远卡在 pending。

    - 若 session 当前不在事务中（调用方已 commit），立即发送
    - 否则注册 after_commit 回调，commit 后再发送（once=True 确保仅触发一次，
      避免共享 session 多次 commit 时重复入队造成重复推送）
    """
    if not db.in_transaction():
        _do_send_task(channel, log_id)
        return

    def _trigger(_session) -> None:
        _do_send_task(channel, log_id)

    event.listen(db, "after_commit", _trigger, once=True)


def _resolve_rule_cfg(db: Session, event_code: str) -> dict:
    """读取飞书通道的 rules 配置"""
    if not is_feishu_enabled(db):
        return {}
    cfg = get_feishu_settings_raw(db)
    rule = (cfg.get("rules") or {}).get(event_code)
    if rule:
        return rule
    return {}


def _get_user_personal_targets(db: Session, user: User) -> list[PushTarget]:
    targets: list[PushTarget] = []
    if (user.feishu_open_id or "").strip() and is_feishu_enabled(db):
        targets.append(PushTarget.user("feishu", user.feishu_open_id.strip(), user_id=user.id))
    return targets


def _get_group_targets_for_event(
    db: Session,
    event_code: str,
    group_codes: list[str] | None = None,
) -> list[PushTarget]:
    if group_codes is None:
        group_codes = EVENT_GROUP_CODES.get(event_code, [])

    feishu_cfg = get_feishu_settings_raw(db) if is_feishu_enabled(db) else {}

    targets: list[PushTarget] = []
    # 飞书 chat_id 跨 group 去重（management/factory 经常复用同一群）
    seen_feishu_chat: set[str] = set()

    for gcode in group_codes:
        f_group = next(
            (g for g in (feishu_cfg.get("groups") or []) if g.get("code") == gcode and g.get("enabled", True)),
            None,
        )
        if not f_group:
            continue
        channels = f_group.get("channels") or {}
        feishu_ch = channels.get("feishu") or {}
        if feishu_ch.get("enabled", True) and (feishu_ch.get("chat_id") or "").strip():
            chat_id = feishu_ch["chat_id"].strip()
            if chat_id not in seen_feishu_chat:
                seen_feishu_chat.add(chat_id)
                targets.append(PushTarget.chat("feishu", chat_id, group_code=gcode))

    return targets


def _create_log(
    db: Session,
    *,
    event_code: str,
    target: PushTarget,
    title: str,
    content: str,
    level: str,
    biz_type: str | None,
    biz_id: int | None,
    payload: dict,
    scheduled_at: datetime | None,
    user: User | None = None,
) -> FeishuPushLog | None:
    if target["channel"] != "feishu":
        return None
    status = "deferred" if scheduled_at and scheduled_at > datetime.now() else "pending"
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
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def _dispatch_targets(
    db: Session,
    *,
    event_code: str,
    targets: list[PushTarget],
    title: str,
    content: str,
    level: str,
    biz_type: str | None,
    biz_id: int | None,
    payload: dict,
    scheduled_at: datetime | None,
    user: User | None = None,
) -> int:
    created = 0
    for target in targets:
        log = _create_log(
            db,
            event_code=event_code,
            target=target,
            title=title,
            content=content,
            level=level,
            biz_type=biz_type,
            biz_id=biz_id,
            payload=payload,
            scheduled_at=scheduled_at,
            user=user,
        )
        if log and log.status == "pending":
            # 关键：等事务 commit 后再 enqueue，避免 worker 用新 session
            # 查到 log_not_found（push_log 此时还未持久化）
            enqueue_after_commit(db, target["channel"], log.id)
        created += 1
    return created


def dispatch(
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
    scheduled_at: datetime | None = None,
) -> int:
    """统一消息分发入口（开源版仅产出飞书通道 log）。"""
    payload = payload or {}
    created = 0

    if is_personal_event(event_code):
        if user_id:
            user = db.get(User, user_id)
            if user and user.is_active:
                created += _dispatch_targets(
                    db,
                    event_code=event_code,
                    targets=_get_user_personal_targets(db, user),
                    title=title,
                    content=content,
                    level=level,
                    biz_type=biz_type,
                    biz_id=biz_id,
                    payload=payload,
                    scheduled_at=scheduled_at,
                    user=user,
                )
        return created

    if is_rule_based_event(event_code):
        rule = _resolve_rule_cfg(db, event_code)
        target_codes = rule.get("targets") or ["dept_leaders", "workshop_leaders"]

        from app.services.feishu.targets import notify_in_app_for_targets, resolve_targets

        user_targets = resolve_targets(
            db,
            target_codes,
            user_id=user_id,
            department_id=department_id,
            workshop=workshop,
        )
        notify_in_app_for_targets(
            db,
            target_codes,
            title=title,
            content=content,
            level=level,
            biz_type=biz_type,
            biz_id=biz_id,
            user_id=user_id,
            department_id=department_id,
            workshop=workshop,
        )
        seen_user_ids: set[int] = set()
        for t in user_targets:
            if t.get("kind") != "user":
                continue
            uid = t.get("user_id")
            if not uid or uid in seen_user_ids:
                continue
            seen_user_ids.add(uid)
            user = db.get(User, uid)
            if not user or not user.is_active:
                continue
            created += _dispatch_targets(
                db,
                event_code=event_code,
                targets=_get_user_personal_targets(db, user),
                title=title,
                content=content,
                level=level,
                biz_type=biz_type,
                biz_id=biz_id,
                payload=payload,
                scheduled_at=scheduled_at,
                user=user,
            )
        return created

    if is_group_only_event(event_code):
        return _dispatch_targets(
            db,
            event_code=event_code,
            targets=_get_group_targets_for_event(db, event_code),
            title=title,
            content=content,
            level=level,
            biz_type=biz_type,
            biz_id=biz_id,
            payload=payload,
            scheduled_at=scheduled_at,
        )

    if is_mixed_event(event_code):
        if user_id:
            user = db.get(User, user_id)
            if user:
                created += _dispatch_targets(
                    db,
                    event_code=event_code,
                    targets=_get_user_personal_targets(db, user),
                    title=title,
                    content=content,
                    level=level,
                    biz_type=biz_type,
                    biz_id=biz_id,
                    payload=payload,
                    scheduled_at=scheduled_at,
                    user=user,
                )
        created += _dispatch_targets(
            db,
            event_code=event_code,
            targets=_get_group_targets_for_event(db, event_code),
            title=title,
            content=content,
            level=level,
            biz_type=biz_type,
            biz_id=biz_id,
            payload=payload,
            scheduled_at=scheduled_at,
        )
        return created

    return 0