"""生产计划投产前就绪检查：齐套、工艺路线、工价"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.material_bom import get_effective_bom_map_by_sku_ids
from app.crud.order import get_order_by_id
from app.crud.process_price import get_price_by_sku_process
from app.crud.production_plan import get_plan_by_id
from app.crud.warehouse import sum_stock_qty_by_sku_ids
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.services.display_label import process_display_name, product_display_name, sku_display_name
from app.services.entity_refs import missing_bom_dict


def _kitting_section(db: Session, tenant_id: int, order) -> dict:
    sku_qty: dict[int, int] = {}
    for it in order.items:
        sku_qty[it.sku_id] = sku_qty.get(it.sku_id, 0) + it.qty
    sku_ids = list(sku_qty.keys())

    bom_by_sku = get_effective_bom_map_by_sku_ids(db, tenant_id=tenant_id, sku_ids=sku_ids)
    missing_boms = []
    for it in order.items:
        if it.sku and it.sku_id not in bom_by_sku:
            row = missing_bom_dict(it.sku, getattr(it.sku, "product", None))
            row["hint"] = "可配置全厂默认 BOM 或产品默认 BOM"
            missing_boms.append(row)

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
                "unit": m.unit,
                "spec": m.spec,
                "supplier_id": m.supplier_id,
                "sku_id": m.sku_id,
            }

    stock_map = sum_stock_qty_by_sku_ids(
        db, tenant_id=tenant_id, sku_ids=[v["sku_id"] for v in material_meta.values() if v.get("sku_id")]
    )
    items = []
    shortage_count = 0
    for mid, demand_qty in demand_by_material.items():
        meta = material_meta[mid]
        stock_qty = stock_map.get(meta["sku_id"], 0) if meta.get("sku_id") else 0
        shortage_qty = max(0, demand_qty - stock_qty)
        if shortage_qty > 0:
            shortage_count += 1
        items.append({**meta, "demand_qty": demand_qty, "stock_qty": stock_qty, "shortage_qty": shortage_qty})
    items.sort(key=lambda x: (x["shortage_qty"] == 0, x["material_id"]))

    return {
        "items": items,
        "missing_boms": missing_boms,
        "shortage_count": shortage_count,
        "missing_bom_count": len(missing_boms),
        "ok": shortage_count == 0 and len(missing_boms) == 0,
    }


def _process_section(db: Session, tenant_id: int, order) -> dict:
    product_ids: set[int] = set()
    for it in order.items:
        if it.sku:
            product_ids.add(it.sku.product_id)

    if not product_ids:
        return {
            "missing_routes": [],
            "missing_prices": [],
            "missing_route_count": 0,
            "missing_price_count": 0,
            "ok": True,
        }

    routes = db.scalars(
        select(ProcessRoute)
        .where(
            ProcessRoute.tenant_id == tenant_id,
            ProcessRoute.product_id.in_(product_ids),
            ProcessRoute.is_default.is_(True),
            ProcessRoute.is_active.is_(True),
        )
        .options(selectinload(ProcessRoute.steps).selectinload(ProcessRouteStep.process))
    ).all()
    route_by_product = {r.product_id: r for r in routes}

    missing_routes = []
    seen_products: dict[int, object] = {}
    for it in order.items:
        if it.sku and it.sku.product_id not in seen_products:
            seen_products[it.sku.product_id] = it.sku.product

    for pid, product in seen_products.items():
        route = route_by_product.get(pid)
        if not route or not route.steps:
            missing_routes.append(
                {
                    "product_id": pid,
                    "product_code": product.code,
                    "product_name": product_display_name(product.name, product.description, product.code, product.category),
                }
            )

    missing_prices = []
    for it in order.items:
        if not it.sku:
            continue
        route = route_by_product.get(it.sku.product_id)
        if not route or not route.steps:
            continue
        for step in sorted(route.steps, key=lambda s: s.seq):
            proc = step.process
            if not proc:
                continue
            price = get_price_by_sku_process(db, tenant_id, it.sku_id, proc.id)
            if not price or not price.is_active:
                product = getattr(it.sku, "product", None)
                pn = product_display_name(
                    product.name, product.description, product.code, product.category
                ) if product else ""
                sm = sku_display_name(it.sku.name, it.sku.code)
                missing_prices.append(
                    {
                        "sku_id": it.sku_id,
                        "sku_code": it.sku.code,
                        "sku_name": sm,
                        "product_id": it.sku.product_id,
                        "product_name": pn,
                        "display_label": f"{pn} · {sm}" if pn else sm,
                        "process_id": proc.id,
                        "process_code": proc.code,
                        "process_name": process_display_name(proc.name, proc.code),
                    }
                )

    # dedupe missing_prices by sku_id+process_id
    dedup: dict[tuple[int, int], dict] = {}
    for row in missing_prices:
        dedup[(row["sku_id"], row["process_id"])] = row
    missing_prices = list(dedup.values())

    return {
        "missing_routes": missing_routes,
        "missing_prices": missing_prices,
        "missing_route_count": len(missing_routes),
        "missing_price_count": len(missing_prices),
        "ok": len(missing_routes) == 0 and len(missing_prices) == 0,
    }


def build_order_kitting_preview(db: Session, tenant_id: int, order_id: int) -> dict | None:
    """任意状态订单的物料齐套预览（不要求已审核）。"""
    order = get_order_by_id(db, tenant_id=tenant_id, order_id=order_id, with_items=True)
    if not order or not order.items:
        return None
    return _kitting_section(db, tenant_id, order)


def build_plan_readiness(
    db: Session,
    tenant_id: int,
    *,
    order_id: int,
    plan_id: int | None = None,
) -> dict:
    order = get_order_by_id(db, tenant_id=tenant_id, order_id=order_id, with_items=True)
    if not order:
        raise ValueError("订单不存在")
    if order.status != "confirmed":
        raise ValueError("仅已审核订单可做投产就绪检查")

    plan_code = None
    if plan_id:
        plan = get_plan_by_id(db, tenant_id=tenant_id, plan_id=plan_id)
        if plan and plan.order_id == order_id:
            plan_code = plan.code

    kitting = _kitting_section(db, tenant_id, order)
    process = _process_section(db, tenant_id, order)

    blockers = []
    if kitting["missing_bom_count"]:
        blockers.append(f"{kitting['missing_bom_count']} 个型号未配置 BOM")
    if kitting["shortage_count"]:
        blockers.append(f"{kitting['shortage_count']} 项物料缺料")
    if process["missing_route_count"]:
        blockers.append(f"{process['missing_route_count']} 个产品未配置默认工艺路线")
    if process["missing_price_count"]:
        blockers.append(f"{process['missing_price_count']} 条型号工序工价缺失")

    return {
        "plan_id": plan_id,
        "plan_code": plan_code,
        "order_id": order.id,
        "order_code": order.code,
        "customer_name": order.customer.name if order.customer else None,
        "kitting": kitting,
        "process": process,
        "ready": kitting["ok"] and process["ok"],
        "blockers": blockers,
    }
