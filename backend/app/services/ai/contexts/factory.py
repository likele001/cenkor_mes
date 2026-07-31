"""全厂管理助手：聚合仪表盘、订单、计划、齐套、进度、预警等上下文。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.dashboard import get_dashboard_summary
from app.crud.kanban import list_kanban_orders
from app.crud.order import list_orders
from app.crud.production_plan import list_plans_with_order_info
from app.models.order import Order
from app.models.task import Task
from app.services.ai.alerts import list_recent_alerts
from app.services.ai.contexts.factory_extended import (
    build_cost_context,
    build_crm_context,
    build_equipment_context,
    build_purchase_context,
)
from app.services.display_label import order_sku_option_label
from app.services.plan_readiness import build_order_kitting_preview, build_plan_readiness


def _order_sku_summary(order: Order) -> str | None:
    labels: list[str] = []
    for it in order.items or []:
        sku = getattr(it, "sku", None)
        if not sku:
            continue
        product = getattr(sku, "product", None)
        _, _, label = order_sku_option_label(
            product_name=product.name if product else None,
            product_description=product.description if product else None,
            product_code=product.code if product else None,
            product_category=product.category if product else None,
            sku_name=sku.name,
            sku_code=sku.code,
            sku_color=sku.color,
            sku_material=sku.material,
            sku_spec=sku.spec,
        )
        labels.append(f"{label} x{it.qty}")
    return "，".join(labels) if labels else None


def _order_total_qty(order: Order) -> int:
    return sum(int(getattr(it, "qty", 0) or 0) for it in (order.items or []))


def _shortage_rows(kitting: dict, *, limit: int = 5) -> list[dict]:
    rows = []
    for it in kitting.get("items") or []:
        sq = int(it.get("shortage_qty") or 0)
        if sq <= 0:
            continue
        rows.append(
            {
                "material_code": it.get("material_code"),
                "material_name": it.get("material_name"),
                "demand_qty": it.get("demand_qty"),
                "stock_qty": it.get("stock_qty"),
                "shortage_qty": sq,
                "unit": it.get("unit"),
            }
        )
    rows.sort(key=lambda x: int(x.get("shortage_qty") or 0), reverse=True)
    return rows[:limit]


def _plan_readiness_snapshot(db: Session, tenant_id: int, *, order_id: int, plan_id: int, order_status: str) -> dict:
    if order_status == "confirmed":
        try:
            r = build_plan_readiness(db, tenant_id=tenant_id, order_id=order_id, plan_id=plan_id)
            kitting = r.get("kitting") or {}
            process = r.get("process") or {}
            return {
                "ready": r.get("ready"),
                "blockers": r.get("blockers") or [],
                "shortage_count": kitting.get("shortage_count", 0),
                "missing_bom_count": kitting.get("missing_bom_count", 0),
                "missing_route_count": process.get("missing_route_count", 0),
                "missing_price_count": process.get("missing_price_count", 0),
                "shortages": _shortage_rows(kitting),
                "missing_boms": (kitting.get("missing_boms") or [])[:5],
            }
        except ValueError as e:
            return {"ready": False, "blockers": [str(e)], "shortages": []}
    kitting = build_order_kitting_preview(db, tenant_id, order_id)
    if not kitting:
        return {"ready": None, "blockers": ["订单无明细"], "shortages": []}
    blockers = []
    if kitting.get("missing_bom_count"):
        blockers.append(f"{kitting['missing_bom_count']} 个型号未配置 BOM")
    if kitting.get("shortage_count"):
        blockers.append(f"{kitting['shortage_count']} 项物料缺料")
    return {
        "ready": kitting.get("ok"),
        "blockers": blockers,
        "shortage_count": kitting.get("shortage_count", 0),
        "missing_bom_count": kitting.get("missing_bom_count", 0),
        "shortages": _shortage_rows(kitting),
        "missing_boms": (kitting.get("missing_boms") or [])[:5],
        "note": "订单未审核，齐套为预览数据",
    }


def build_factory_context(db: Session, tenant_id: int, *, plan_id: int | None = None) -> dict:
    dashboard = get_dashboard_summary(db, tenant_id=tenant_id)

    status_rows = db.execute(
        select(Order.status, func.count(Order.id))
        .where(Order.tenant_id == tenant_id)
        .group_by(Order.status)
    ).all()
    orders_by_status = {str(s): int(c) for s, c in status_rows}

    pending_review: list[dict] = []
    recent_orders = list_orders(db, tenant_id=tenant_id, limit=30)
    for o in recent_orders:
        if o.status != "pending_confirm":
            continue
        cust = o.customer
        kitting = build_order_kitting_preview(db, tenant_id, o.id)
        pending_review.append(
            {
                "id": o.id,
                "code": o.code,
                "customer_name": cust.name if cust else None,
                "total_qty": _order_total_qty(o),
                "sku_summary": _order_sku_summary(o),
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "kitting_preview": {
                    "ok": kitting.get("ok") if kitting else None,
                    "shortage_count": kitting.get("shortage_count") if kitting else 0,
                    "missing_bom_count": kitting.get("missing_bom_count") if kitting else 0,
                    "top_shortages": _shortage_rows(kitting or {}, limit=3),
                },
            }
        )
        if len(pending_review) >= 8:
            break

    progress_orders = list_kanban_orders(
        db,
        tenant_id=tenant_id,
        status="producing",
        limit=10,
    )
    if not progress_orders:
        progress_orders = list_kanban_orders(db, tenant_id=tenant_id, status="confirmed", limit=8)

    plan_rows = list_plans_with_order_info(
        db,
        tenant_id=tenant_id,
        limit=15,
    )
    production_plans: list[dict] = []
    all_shortages: list[dict] = []
    for plan, order_code, order_status, customer_name, qty in plan_rows:
        if plan.status not in ("planned", "in_progress"):
            continue
        readiness = _plan_readiness_snapshot(
            db, tenant_id, order_id=plan.order_id, plan_id=plan.id, order_status=str(order_status or "")
        )
        for s in readiness.get("shortages") or []:
            all_shortages.append({**s, "plan_code": plan.code, "order_code": order_code})
        production_plans.append(
            {
                "plan_id": plan.id,
                "plan_code": plan.code,
                "status": plan.status,
                "order_id": plan.order_id,
                "order_code": order_code,
                "order_status": order_status,
                "customer_name": customer_name,
                "qty": int(qty or 0),
                "start_date": plan.start_date.isoformat() if plan.start_date else None,
                "end_date": plan.end_date.isoformat() if plan.end_date else None,
                "readiness": readiness,
            }
        )

    all_shortages.sort(key=lambda x: int(x.get("shortage_qty") or 0), reverse=True)

    unassigned = int(
        db.scalar(
            select(func.count(Task.id)).where(
                Task.tenant_id == tenant_id,
                Task.status == "pending",
            )
        )
        or 0
    )

    alerts = list_recent_alerts(db, tenant_id, limit=6)

    ctx: dict = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "scope": "全厂管理",
        "dashboard": dashboard,
        "orders": {
            "by_status": orders_by_status,
            "pending_review": pending_review,
            "pending_review_count": orders_by_status.get("pending_confirm", 0),
        },
        "order_progress": progress_orders,
        "production_plans": production_plans,
        "material_overview": {
            "plans_tracked": len(production_plans),
            "plans_not_ready": sum(1 for p in production_plans if p.get("readiness", {}).get("ready") is False),
            "top_shortages_factory_wide": all_shortages[:12],
        },
        "tasks": {
            "pending_unassigned_estimate": unassigned,
            "pending": dashboard.get("tasks", {}).get("pending"),
            "done": dashboard.get("tasks", {}).get("done"),
        },
        "alerts": alerts,
        "cost_profit": build_cost_context(db, tenant_id, dashboard=dashboard),
        "crm": build_crm_context(db, tenant_id),
        "purchase": build_purchase_context(db, tenant_id),
        "equipment": build_equipment_context(db, tenant_id),
    }

    if plan_id:
        from app.services.ai.contexts.plan import build_plan_context

        focus = build_plan_context(db, tenant_id, plan_id)
        if focus:
            order_id = focus.get("order", {}).get("id")
            if order_id:
                kitting = build_order_kitting_preview(db, tenant_id, int(order_id))
                if kitting:
                    focus["kitting_detail"] = {
                        "shortage_count": kitting.get("shortage_count"),
                        "missing_bom_count": kitting.get("missing_bom_count"),
                        "items": (kitting.get("items") or [])[:20],
                        "missing_boms": kitting.get("missing_boms") or [],
                    }
            ctx["focus_plan"] = focus

    return ctx
