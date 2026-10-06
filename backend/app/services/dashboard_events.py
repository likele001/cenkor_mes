# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""看板实时刷新：把「看板读的表被提交了」转成 WebSocket 刷新事件。

挂在 Session 类级事件上，而不是逐个端点手写调用——看板的数据来自
Report / ReportUnit / Order / WorkOrder / Task / TaskAssignment / SalaryItem，
这些表的写入点散落在 admin、h5、自动化、脚本各处，逐个补必漏。

只认「事务真的 commit 了」：flush 时记下变更的表，commit 才广播，
rollback 直接丢弃，避免大屏被一次失败的操作误导重载。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.report import Report
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.work_order import WorkOrder
from app.services.ws_hub import dashboard_ws_hub

logger = logging.getLogger(__name__)

_SESSION_KEY = "dashboard_changed_channels"

# 模型 -> 看板数据块（前端目前只认 type=refresh，channel 供后续按需局部刷新）
_WATCHED: tuple[tuple[type, str], ...] = (
    (Report, "reports"),
    (ReportUnit, "reports"),
    (ReportUnitAudit, "reports"),
    (Order, "orders"),
    (OrderItem, "orders"),
    (WorkOrder, "orders"),
    (Task, "tasks"),
    (TaskAssignment, "tasks"),
    (SalaryItem, "salary"),
)

_MODEL_CHANNEL: dict[str, str] = {cls.__name__: ch for cls, ch in _WATCHED}


def _channel_for(obj: Any) -> str | None:
    # 用类名查表，避免 SQLAlchemy 子类/代理对象让 isinstance 判断失真
    return _MODEL_CHANNEL.get(type(obj).__name__)


def record_dirty_channels(session: Session) -> None:
    """flush 前把本次事务改到的看板表记进 session.info。"""
    channels: set[str] = session.info.setdefault(_SESSION_KEY, set())
    for group in (session.new, session.dirty, session.deleted):
        for obj in group:
            ch = _channel_for(obj)
            if ch:
                channels.add(ch)


def changed_channels(session: Session) -> set[str]:
    return set(session.info.get(_SESSION_KEY) or ())


def flush_refresh(session: Session, *, reason: str = "commit") -> bool:
    """commit 后广播刷新事件，并清空累计的变更标记。"""
    channels = session.info.pop(_SESSION_KEY, None)
    if not channels:
        return False
    try:
        return dashboard_ws_hub.publish_refresh(channels, reason=reason)
    except Exception as e:  # 推送失败绝不能连累已提交的业务事务
        logger.warning("dashboard ws refresh failed: %s", e)
        return False


def discard_refresh(session: Session) -> None:
    session.info.pop(_SESSION_KEY, None)


@event.listens_for(Session, "before_flush")
def _on_before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    record_dirty_channels(session)


@event.listens_for(Session, "after_commit")
def _on_after_commit(session: Session) -> None:
    flush_refresh(session)


@event.listens_for(Session, "after_rollback")
def _on_after_rollback(session: Session) -> None:
    discard_refresh(session)
