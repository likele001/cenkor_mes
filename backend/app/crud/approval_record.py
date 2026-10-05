# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""审批留痕写入与查询。

单据状态每次翻转都追加一行，历史不覆盖。留痕写失败就让它抛：留痕是审计资产，
静默丢记录比让业务动作一起失败更糟。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.approval_record import ApprovalRecord
from app.models.user import User

# 状态名 → 留痕动作名：留痕要能按动作检索，不该统一写成 status_change
STATUS_ACTION_MAP = {
    "confirmed": "confirm",
    "partial": "pay",
    "paid": "pay",
    "cancelled": "cancel",
    "canceled": "cancel",
    "draft": "reset",
    "rejected": "reject",
}


def status_action(status: str | None) -> str:
    return STATUS_ACTION_MAP.get(status or "", "status_change")


def record_status(
    db: Session,
    *,
    biz_type: str,
    biz_id: int,
    action: str,
    operator: User | int | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    biz_code: str | None = None,
    reason: str | None = None,
    channel: str = "web",
    detail: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> ApprovalRecord:
    """追加一条状态变更留痕。operator 传 User 对象或用户 id 都行。"""
    operator_id: int | None = None
    operator_name: str | None = None
    if isinstance(operator, User):
        operator_id = operator.id
        operator_name = operator.full_name or operator.username
    elif isinstance(operator, int):
        operator_id = operator
        user = db.get(User, operator)
        if user:
            operator_name = user.full_name or user.username

    row = ApprovalRecord(
        biz_type=biz_type,
        biz_id=biz_id,
        biz_code=biz_code,
        action=action,
        from_status=from_status,
        to_status=to_status,
        operator_id=operator_id,
        operator_name=operator_name,
        channel=channel,
        reason=reason or None,
        detail=json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
        **({"created_at": created_at} if created_at else {}),
    )
    db.add(row)
    db.flush()
    return row


def list_records(
    db: Session,
    *,
    biz_type: str | None = None,
    biz_id: int | None = None,
    operator_id: int | None = None,
    action: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[ApprovalRecord], int]:
    conditions = []
    if biz_type:
        conditions.append(ApprovalRecord.biz_type == biz_type)
    if biz_id is not None:
        conditions.append(ApprovalRecord.biz_id == biz_id)
    if operator_id is not None:
        conditions.append(ApprovalRecord.operator_id == operator_id)
    if action:
        conditions.append(ApprovalRecord.action == action)

    stmt = select(ApprovalRecord)
    count_stmt = select(func.count()).select_from(ApprovalRecord)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = int(db.scalar(count_stmt) or 0)
    items = db.scalars(
        stmt.order_by(ApprovalRecord.id.desc()).offset(offset).limit(limit)
    ).all()
    return list(items), total
