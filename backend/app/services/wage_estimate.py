# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""报工即时预估工资：与终审生成 SalaryItem 的口径保持一致。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.process_price import ProcessPrice
from app.models.task import Task
from app.models.work_order import WorkOrder


def estimate_wage(db: Session, task: Task | None, good_qty: int) -> dict:
    empty = {"unit_price": 0.0, "amount": 0.0, "priced": False}
    if task is None or good_qty is None or int(good_qty) <= 0:
        return empty
    wo = db.get(WorkOrder, task.work_order_id)
    if not wo or not task.process_id:
        return empty
    price = db.scalar(
        select(ProcessPrice.unit_price).where(
            ProcessPrice.sku_id == wo.sku_id,
            ProcessPrice.process_id == task.process_id,
            ProcessPrice.is_active.is_(True),
        )
    )
    if price is None:
        return empty
    unit_price = Decimal(str(price))
    amount = unit_price * Decimal(int(good_qty))
    return {
        "unit_price": float(unit_price),
        "amount": float(amount),
        "priced": True,
    }
