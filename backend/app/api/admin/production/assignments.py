"""分工分配列表（按员工×任务维度，对标 thinkmes 分工分配）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.task_assignment import get_assignment_by_id, list_assignments, remove_assignment_by_id, sum_user_reported_qty

from app.models.user import User
from app.services.display_label import process_display_name, product_display_name, sku_display_name, sku_option_extra_fields
from app.services.task_qr import task_qr_payload


router = APIRouter(dependencies=[Depends(require_permissions(["dispatch.manage"]))])


def _status_label(reported: int, assigned: int) -> str:
    if assigned <= 0:
        return "pending"
    if reported >= assigned:
        return "done"
    if reported > 0:
        return "working"
    return "pending"


def _row_out(a, db: Session) -> dict:
    task = a.task
    wo = task.work_order if task else None
    order = wo.order if wo else None
    sku = wo.sku if wo else None
    product = wo.product if wo else None
    proc = task.process if task else None
    u = a.user
    reported = sum_user_reported_qty(db, task.id, a.user_id) if task else 0
    assigned = int(a.assigned_qty)
    remaining = max(0, assigned - reported)
    progress = int(round(reported * 100 / assigned)) if assigned > 0 else 0
    pn = product_display_name(product.name, product.description, product.code, product.category) if product else ""
    sm = sku_display_name(sku.name, sku.code) if sku else ""
    display_label = ""
    if sku:
        extra = sku_option_extra_fields(
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
        display_label = extra["display_label"]
    return {
        "id": a.id,
        "task_id": task.id if task else None,
        "task_code": task.task_code if task else None,
        "task_status": task.status if task else None,
        "order_id": order.id if order else None,
        "order_code": order.code if order else None,
        "product_id": product.id if product else None,
        "product_name": pn or (product.name if product else None),
        "sku_id": sku.id if sku else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sm or (sku.name if sku else None),
        "display_label": display_label or None,
        "process_id": proc.id if proc else None,
        "process_code": proc.code if proc else None,
        "process_name": process_display_name(proc.name, proc.code) if proc else None,
        "user_id": a.user_id,
        "username": u.username if u else None,
        "user_full_name": u.full_name if u else None,
        "assigned_qty": assigned,
        "reported_qty": reported,
        "remaining_qty": remaining,
        "progress": progress,
        "status": _status_label(reported, assigned),
        "assigned_at": a.assigned_at,
        "assigned_by": a.assigned_by,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    order_id: int | None = Query(default=None, ge=1),
    user_id: int | None = Query(default=None, ge=1),
    process_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = list_assignments(db, keyword=keyword,
        order_id=order_id,
        user_id=user_id,
        process_id=process_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_row_out(x, db) for x in rows], "total": total})


@router.get("/{assignment_id}/qr")
def assignment_qr_api(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = get_assignment_by_id(db, assignment_id=assignment_id)
    if not a or not a.task:
        raise HTTPException(status_code=404, detail="派工记录不存在")
    payload = task_qr_payload(a.task.task_code)
    payload["assignment_id"] = a.id
    payload["user_id"] = a.user_id
    return ok(payload)


@router.delete("/{assignment_id}")
def delete_api(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        remove_assignment_by_id(db, assignment_id=assignment_id, dispatcher_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok()
