# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""把存量汇总库存回填成批次账（0023 之后一次性初始化）。

背景
----
0023 建出了 `stock_batch`（批次库存），但存量库的库存只记在 `stocks`
汇总表里。不做这一步初始化：`stocks` 说有 100 件，`stock_batch` 一行没有 ——
拓展一算就是满仓盘亏，FIFO 出库直接报「无可用批次」。

做两件事
--------
1. **每个仓库建 DEFAULT 库区 + DEFAULT 库位**。库位化之后所有出入库都要落到
   具体库位，老数据没有库位信息，只能先集中挂到默认库位上。
2. **每条 `stocks(qty > 0)` 生成一条 `stock_batch`**：

   ==================  ====================================================
   batch_no            ``LEGACY-{sku_id}``，LEGACY 前缀一眼能看出是历史迁移
   location_id         该仓 DEFAULT 库位
   qty_on_hand         ``stocks.qty``
   status              ``qualified``（历史在账库存视为合格品）
   source_type         ``legacy_backfill``
   ==================  ====================================================

**不写 `stock_ledger`**：这批库存没有发生真实出入库事件，凭空补一条流水会
污染 FIFO 报表和库龄统计。流水从这次初始化之后的新业务开始记。

幂等
----
- 库区/库位按 `(tenant_id, warehouse_id, code)` 查，命中就复用
- 批次按 `(tenant_id, warehouse_id, location_id, sku_id, batch_no)` 查，命中就跳过
- 重复执行结果完全一致

自检
----
跑完会核对每个仓库的 `sum(stock_batch.qty_on_hand) == sum(stocks.qty)`，
不一致直接把差行列出来并以非零码退出 —— 宁可报错也不要留两套账。

用法
----
    cd backend
    python3 -m scripts.init_warehouse_bins --dry-run    # 只打印计划，不落库
    python3 -m scripts.init_warehouse_bins              # 真跑
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.tenant import Tenant
from app.models.warehouse import (
    Stock,
    StockBatch,
    Warehouse,
    WarehouseLocation,
    WarehouseZone,
)

DEFAULT_ZONE_CODE = "DEFAULT"
DEFAULT_ZONE_NAME = "默认库区"
DEFAULT_LOC_CODE = "DEFAULT"
DEFAULT_LOC_NAME = "默认库位"
LEGACY_BATCH_PREFIX = "LEGACY-"
SOURCE_TYPE = "legacy_backfill"


def _resolve_tenant_id(db: Session) -> int:
    """单用户版固定单租户，但要真去表里查 —— 外键指向 tenants.id，硬编码 1 可能撞空表。"""
    tid = db.scalar(select(Tenant.id).order_by(Tenant.id).limit(1))
    if tid is None:
        raise SystemExit("tenants 表为空：单用户版至少要有 id=1 的租户记录，先跑 seed")
    return int(tid)


def ensure_default_zone(db: Session, tenant_id: int, warehouse: Warehouse) -> tuple[WarehouseZone, bool]:
    """返回 (库区, 是否新建)。"""
    zone = db.scalar(
        select(WarehouseZone).where(
            WarehouseZone.tenant_id == tenant_id,
            WarehouseZone.warehouse_id == warehouse.id,
            WarehouseZone.code == DEFAULT_ZONE_CODE,
        )
    )
    if zone is not None:
        return zone, False
    zone = WarehouseZone(
        tenant_id=tenant_id,
        warehouse_id=warehouse.id,
        code=DEFAULT_ZONE_CODE,
        name=DEFAULT_ZONE_NAME,
        zone_type="storage",
        sort_order=0,
        enabled=True,
    )
    db.add(zone)
    db.flush()
    return zone, True


def ensure_default_location(
    db: Session, tenant_id: int, warehouse: Warehouse, zone: WarehouseZone
) -> tuple[WarehouseLocation, bool]:
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.tenant_id == tenant_id,
            WarehouseLocation.warehouse_id == warehouse.id,
            WarehouseLocation.code == DEFAULT_LOC_CODE,
        )
    )
    if loc is not None:
        return loc, False
    loc = WarehouseLocation(
        tenant_id=tenant_id,
        warehouse_id=warehouse.id,
        code=DEFAULT_LOC_CODE,
        name=DEFAULT_LOC_NAME,
        zone_id=zone.id,
        location_type="bin",
        is_active=True,
        remark="历史库存迁移自动创建",
    )
    db.add(loc)
    db.flush()
    return loc, True


def backfill_batches(
    db: Session, tenant_id: int, warehouse: Warehouse, loc: WarehouseLocation, dry_run: bool
) -> tuple[int, int]:
    """把该仓 qty>0 的汇总库存转成 LEGACY 批次行。返回 (新建数, 跳过数)。"""
    created = skipped = 0
    rows = db.scalars(
        select(Stock).where(Stock.warehouse_id == warehouse.id, Stock.qty > 0).order_by(Stock.sku_id)
    ).all()
    for st in rows:
        batch_no = f"{LEGACY_BATCH_PREFIX}{st.sku_id}"
        exists = db.scalar(
            select(StockBatch.id).where(
                StockBatch.tenant_id == tenant_id,
                StockBatch.warehouse_id == warehouse.id,
                StockBatch.location_id == loc.id,
                StockBatch.sku_id == st.sku_id,
                StockBatch.batch_no == batch_no,
            )
        )
        if exists is not None:
            skipped += 1
            continue
        if dry_run:
            print(f"    + 批次 {batch_no:16s} sku={st.sku_id:<6d} 数量={st.qty}")
            created += 1
            continue
        db.add(
            StockBatch(
                tenant_id=tenant_id,
                warehouse_id=warehouse.id,
                location_id=loc.id,
                sku_id=st.sku_id,
                batch_no=batch_no,
                qty_on_hand=int(st.qty or 0),
                qty_reserved=0,
                status="qualified",
                source_type=SOURCE_TYPE,
            )
        )
        created += 1
    return created, skipped


def _verify(db: Session, tenant_id: int) -> list[str]:
    """每个仓库的汇总库存 vs 批次库存，返回差异描述（空表示平）。"""
    problems: list[str] = []
    whs = db.scalars(select(Warehouse).order_by(Warehouse.id)).all()
    for wh in whs:
        book = db.scalar(
            select(func.coalesce(func.sum(Stock.qty), 0)).where(Stock.warehouse_id == wh.id)
        )
        batch = db.scalar(
            select(func.coalesce(func.sum(StockBatch.qty_on_hand), 0)).where(
                StockBatch.tenant_id == tenant_id,
                StockBatch.warehouse_id == wh.id,
            )
        )
        book_i, batch_i = int(book or 0), int(batch or 0)
        if book_i != batch_i:
            problems.append(
                f"{wh.code}({wh.name}) 汇总 {book_i} vs 批次 {batch_i}，差 {book_i - batch_i:+d}"
            )
    return problems


def run(dry_run: bool) -> int:
    db = SessionLocal()
    try:
        tenant_id = _resolve_tenant_id(db)
        whs = db.scalars(select(Warehouse).order_by(Warehouse.id)).all()
        print(f"租户 id={tenant_id}，仓库 {len(whs)} 个，模式={'DRY-RUN' if dry_run else 'EXECUTE'}")
        print()

        total_zone = total_loc = total_batch = total_skip = 0
        for wh in whs:
            print(f"  [{wh.code}] {wh.name}")
            zone, zone_new = ensure_default_zone(db, tenant_id, wh)
            loc, loc_new = ensure_default_location(db, tenant_id, wh, zone)
            if zone_new:
                total_zone += 1
                print(f"    + 库区 {DEFAULT_ZONE_CODE} / {DEFAULT_ZONE_NAME}")
            if loc_new:
                total_loc += 1
                print(f"    + 库位 {DEFAULT_LOC_CODE} / {DEFAULT_LOC_NAME}")
            c, s = backfill_batches(db, tenant_id, wh, loc, dry_run)
            total_batch += c
            total_skip += s

        print()
        print(
            f"合计：新建库区 {total_zone}，新建库位 {total_loc}，"
            f"新建批次 {total_batch}，已存在跳过 {total_skip}"
        )

        if dry_run:
            db.rollback()
            print("DRY-RUN 结束，未写入任何数据（回滚）")
            return 0

        db.commit()
        print("已提交")

        problems = _verify(db, tenant_id)
        if problems:
            print()
            print("对账不平：")
            for p in problems:
                print(f"  ✗ {p}")
            return 1
        print("对账通过：所有仓库的汇总库存与批次库存相等")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="存量库存回填成批次账")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写库")
    args = ap.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
