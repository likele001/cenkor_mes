# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""
只读盘点：账实一致体检报告。

库存扣减校验、发货/外协记仓库这些改动上线前，先看看现网账面到底烂成什么样：
- 账面为负的库存行（历史超扣）
- 库存余额与流水累计对不上的行（漏记流水 / 手工改库）
- 没有仓库归属的发货单与外协收发记录（旧数据，改动后新单据都会带上）

用法: python3 -m scripts.audit_stock_ledger
本脚本只读，不写任何数据。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, select, text as sa_text

from app.core.db import SessionLocal
from app.models.shipment import Shipment
from app.models.subcontract import SubcontractReceiveLog, SubcontractSendLog
from app.models.warehouse import Stock, StockLog


def _has_column(db, table: str, column: str) -> bool:
    """0008 迁移没跑时这几列还不存在，别让盘点脚本先炸在缺列上。"""
    return db.execute(
        sa_text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    ).scalar() > 0


def _count_missing_warehouse(db, model) -> str:
    if not _has_column(db, model.__tablename__, "warehouse_id"):
        return "列未建（待跑 0008）"
    return db.scalar(select(func.count()).select_from(model).where(model.warehouse_id.is_(None)))


def run() -> None:
    db = SessionLocal()
    try:
        negative = db.scalars(select(Stock).where(Stock.qty < 0).order_by(Stock.qty)).all()
        print(f"账面为负的库存行：{len(negative)}")
        for s in negative[:50]:
            print(f"  {s.warehouse_id}/{s.sku_id} 账面 {s.qty}")
        if len(negative) > 50:
            print(f"  ...另有 {len(negative) - 50} 行")

        ledger = db.execute(
            select(StockLog.warehouse_id, StockLog.sku_id, func.sum(StockLog.change_qty))
            .group_by(StockLog.warehouse_id, StockLog.sku_id)
        ).all()
        ledger_map = {(w, k): int(total or 0) for w, k, total in ledger}
        stocks = db.scalars(select(Stock)).all()

        drifted = []
        never_ledgered = []
        for s in stocks:
            key = (s.warehouse_id, s.sku_id)
            if key not in ledger_map:
                if s.qty:
                    never_ledgered.append(s)
                continue
            if int(s.qty or 0) != ledger_map[key]:
                drifted.append((s, ledger_map[key]))

        print(f"\n余额与流水累计不符的库存行：{len(drifted)}")
        for s, expected in drifted[:50]:
            print(f"  仓库#{s.warehouse_id} 型号#{s.sku_id} 账面 {int(s.qty or 0)}，流水累计 {expected}，差 {int(s.qty or 0) - expected}")
        if len(drifted) > 50:
            print(f"  ...另有 {len(drifted) - 50} 行")

        print(f"\n有账面却完全没有流水的库存行：{len(never_ledgered)}（多半是建系统前的期初数）")
        for s in never_ledgered[:20]:
            print(f"  仓库#{s.warehouse_id} 型号#{s.sku_id} 账面 {int(s.qty or 0)}")

        no_wh_ship = _count_missing_warehouse(db, Shipment)
        no_wh_send = _count_missing_warehouse(db, SubcontractSendLog)
        no_wh_recv = _count_missing_warehouse(db, SubcontractReceiveLog)
        print(f"\n缺仓库归属的历史单据：发货 {no_wh_ship} 张，外协发料 {no_wh_send} 条，外协收货 {no_wh_recv} 条")
        print("（新单据都会带仓库；历史行不回填，避免伪造出入库现场）")

        total_logs = db.scalar(select(func.count()).select_from(StockLog))
        print(f"\n库存流水共 {total_logs} 条")
        if negative or drifted:
            print("\n结论：账面已与实际脱节，需要一次实盘校正后再依赖上面的库存看板。")
        else:
            print("\n结论：账面与流水一致，无负库存。")
    finally:
        db.close()


if __name__ == "__main__":
    run()
