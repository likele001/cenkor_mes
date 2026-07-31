"""生产计划齐套检查"""

from sqlalchemy.orm import Session

from app.crud.material_bom import get_effective_bom_map_by_sku_ids
from app.crud.warehouse import sum_stock_qty_by_sku_ids
from app.models.order import Order


def calc_order_kitting_shortages(db: Session, order: Order) -> list[dict]:
    """返回缺料明细（shortage_qty > 0）。"""
    sku_qty: dict[int, int] = {}
    for it in order.items:
        sku_qty[it.sku_id] = sku_qty.get(it.sku_id, 0) + it.qty
    sku_ids = list(sku_qty.keys())
    if not sku_ids:
        return []

    bom_by_sku = get_effective_bom_map_by_sku_ids(db, sku_ids=sku_ids)

    demand_by_material: dict[int, int] = {}
    material_meta: dict[int, dict] = {}
    for sku_id, qty in sku_qty.items():
        bom = bom_by_sku.get(sku_id)
        if not bom:
            continue
        for bi in bom.items:
            m = bi.material
            if not m or not m.is_active:
                continue
            demand_by_material[m.id] = demand_by_material.get(m.id, 0) + bi.qty_per * qty
            material_meta[m.id] = {
                "material_id": m.id,
                "material_code": m.code,
                "material_name": m.name,
                "sku_id": m.sku_id,
            }

    stock_map = sum_stock_qty_by_sku_ids(
        db, sku_ids=[v["sku_id"] for v in material_meta.values() if v.get("sku_id")]
    )
    shortages: list[dict] = []
    for mid, demand_qty in demand_by_material.items():
        meta = material_meta[mid]
        stock_qty = stock_map.get(meta["sku_id"], 0) if meta.get("sku_id") else 0
        shortage_qty = max(0, demand_qty - stock_qty)
        if shortage_qty > 0:
            shortages.append({**meta, "demand_qty": demand_qty, "stock_qty": stock_qty, "shortage_qty": shortage_qty})
    return shortages
