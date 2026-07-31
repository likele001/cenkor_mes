from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.material import Material, Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.user import User


router = APIRouter(dependencies=[Depends(require_permissions(["report.view"]))])


@router.get("/purchase")
def purchase_statistics_api(
    month: str | None = Query(default=None, max_length=7),
    supplier_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(
            PurchaseOrder.supplier_id,
            Supplier.name.label("supplier_name"),
            PurchaseOrderItem.material_id,
            Material.code.label("material_code"),
            Material.name.label("material_name"),
            func.sum(PurchaseOrderItem.qty).label("order_qty"),
            func.sum(PurchaseOrderItem.received_qty).label("received_qty"),
            func.sum(PurchaseOrderItem.returned_qty).label("returned_qty"),
            func.sum(PurchaseOrderItem.qty * PurchaseOrderItem.unit_price).label("order_amount"),
            func.sum(PurchaseOrderItem.received_qty * PurchaseOrderItem.unit_price).label("received_amount"),
            func.sum(PurchaseOrderItem.returned_qty * PurchaseOrderItem.unit_price).label("returned_amount"),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(Material, Material.id == PurchaseOrderItem.material_id)

        .where(PurchaseOrder.status.not_in(["draft", "canceled"]))
    )

    if month:
        # 假设 confirmed_at 是用来算月份的
        stmt = stmt.where(func.date_format(PurchaseOrder.confirmed_at, "%Y-%m") == month)
    
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)

    stmt = stmt.group_by(
        PurchaseOrder.supplier_id,
        Supplier.name,
        PurchaseOrderItem.material_id,
        Material.code,
        Material.name,
    ).order_by(PurchaseOrder.supplier_id, PurchaseOrderItem.material_id)

    rows = db.execute(stmt).all()

    items = []
    for r in rows:
        net_qty = int(r.received_qty or 0) - int(r.returned_qty or 0)
        net_amount = float(r.received_amount or 0) - float(r.returned_amount or 0)
        items.append({
            "supplier_id": r.supplier_id,
            "supplier_name": r.supplier_name,
            "material_id": r.material_id,
            "material_code": r.material_code,
            "material_name": r.material_name,
            "order_qty": int(r.order_qty or 0),
            "received_qty": int(r.received_qty or 0),
            "returned_qty": int(r.returned_qty or 0),
            "net_qty": net_qty,
            "order_amount": float(r.order_amount or 0),
            "received_amount": float(r.received_amount or 0),
            "returned_amount": float(r.returned_amount or 0),
            "net_amount": net_amount,
        })

    return ok({"items": items})
