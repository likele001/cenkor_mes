# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""生产计划齐套检查"""

from sqlalchemy.orm import Session

from app.crud.material_bom import get_effective_bom_map_by_sku_ids
from app.crud.warehouse import sum_stock_qty_by_sku_ids
from app.models.order import Order
from app.services.bom_explosion import explode_bom, explode_net, row_meta


def calc_order_kitting_shortages(db: Session, order: Order) -> list[dict]:
    """返回缺料明细（shortage_qty > 0），半成品按自身库存先扣减。"""
    sku_qty: dict[int, int] = {}
    for it in order.items:
        sku_qty[it.sku_id] = sku_qty.get(it.sku_id, 0) + it.qty
    sku_ids = list(sku_qty.keys())
    if not sku_ids:
        return []

    bom_by_sku = get_effective_bom_map_by_sku_ids(db, sku_ids=sku_ids)

    demand_by_material: dict[int, int] = {}
    sub_shortage: dict[int, int] = {}
    material_meta: dict[int, dict] = {}
    for sku_id, qty in sku_qty.items():
        if sku_id not in bom_by_sku:
            continue
        pre = explode_bom(db, sku_id, qty)
        sub_sku_ids = {r.material.sku_id for r in pre.rows if r.is_sub_assembly}
        sub_stock = (
            sum_stock_qty_by_sku_ids(db, sku_ids=list(sub_sku_ids)) if sub_sku_ids else {}
        )
        result = explode_net(db, sku_id, qty, dict(sub_stock))
        for row in result.rows:
            m = row.material
            if not m or not m.is_active:
                continue
            demand_by_material[m.id] = demand_by_material.get(m.id, 0) + row.qty
            if row.is_sub_assembly:
                sub_shortage[m.id] = sub_shortage.get(m.id, 0) + max(0, row.net_qty or 0)
            prev = material_meta.get(m.id)
            if prev is None or row.level < prev["level"]:
                material_meta[m.id] = row_meta(row)

    stock_map = sum_stock_qty_by_sku_ids(
        db, sku_ids=[v["sku_id"] for v in material_meta.values() if v.get("sku_id")]
    )
    shortages: list[dict] = []
    for mid, demand_qty in demand_by_material.items():
        meta = material_meta[mid]
        stock_qty = stock_map.get(meta["sku_id"], 0) if meta.get("sku_id") else 0
        shortage_qty = (
            sub_shortage.get(mid, 0)
            if meta["is_sub_assembly"]
            else max(0, demand_qty - stock_qty)
        )
        if shortage_qty > 0:
            shortages.append(
                {**meta, "demand_qty": demand_qty, "stock_qty": stock_qty, "shortage_qty": shortage_qty}
            )
    return shortages
