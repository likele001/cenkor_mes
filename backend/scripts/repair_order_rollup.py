# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""
回填历史订单的金额与进度：状态汇总改成派生值后，老数据需要跑一次才对得上。
用法: python3 -m scripts.repair_order_rollup [--dry-run]
汇总本身是幂等的，重复跑不会越跑越偏。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.order import Order
from app.services.production_rollup import (
    recalc_order_amount,
    recalc_order_cost,
    sync_order_progress,
    sync_work_order_progress,
)

TOUCH_STATUSES = ("confirmed", "producing", "completed", "shipped")


def run(dry_run: bool) -> None:
    db = SessionLocal()
    try:
        orders = db.scalars(
            select(Order).where(Order.status.in_(TOUCH_STATUSES)).order_by(Order.id)
        ).all()
        changed = 0
        for order in orders:
            before = (float(order.amount or 0), float(order.cost_amount or 0), order.status, order.actual_completed_at)
            for wo in (order.work_orders or []):
                sync_work_order_progress(db, wo)
            sync_order_progress(db, order)
            recalc_order_amount(db, order)
            recalc_order_cost(db, order)
            after = (float(order.amount or 0), float(order.cost_amount or 0), order.status, order.actual_completed_at)
            if before != after:
                changed += 1
                print(f"{order.code}: 金额 {before[0]:.2f}→{after[0]:.2f} 成本 {before[1]:.2f}→{after[1]:.2f} 状态 {before[2]}→{after[2]}")
        if dry_run:
            db.rollback()
            print(f"[dry-run] 共 {len(orders)} 张订单，{changed} 张需要更新，未写库")
        else:
            db.commit()
            print(f"完成：共 {len(orders)} 张订单，更新 {changed} 张")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="回填订单金额/成本/完工状态")
    parser.add_argument("--dry-run", action="store_true", help="只打印差异，不写库")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
