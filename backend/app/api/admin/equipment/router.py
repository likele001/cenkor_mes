from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.equipment import (
    create_equipment,
    create_equipment_check,
    create_equipment_maintenance_log,
    create_equipment_maintenance_plan,
    delete_equipment_maintenance_plan,
    get_equipment_by_code,
    get_equipment_by_id,
    get_equipment_maintenance_plans,
    get_equipment_maintenance_logs,
    list_equipment,
    list_equipment_checks,
    list_equipment_maintenance_logs,
    list_equipment_maintenance_plans,
    update_equipment,
    update_equipment_maintenance_plan,
)
from app.models.user import User
from app.schemas.equipment import (
    EquipmentCreateIn,
    EquipmentMaintenanceLogCreateIn,
    EquipmentMaintenancePlanCreateIn,
    EquipmentMaintenancePlanUpdateIn,
    EquipmentUpdateIn,
)
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response


def _equipment_code_exists(db: Session, code: str) -> bool:
    return get_equipment_by_code(db, code) is not None


router = APIRouter(dependencies=[Depends(require_permissions(["equipment.manage"]))])


# ==================== 设备 ====================

@router.get("")
def list_equipment_api(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_equipment(db, status=status)
    return ok({"items": [{"id": e.id, "code": e.code, "name": e.name, "model": e.model,
            "workshop": e.workshop, "status": e.status,
            "last_maintenance_date": str(e.last_maintenance_date) if e.last_maintenance_date else None,
            "next_maintenance_date": str(e.next_maintenance_date) if e.next_maintenance_date else None,
            "created_at": e.created_at} for e in items]})


@router.get("/export")
def export_equipment_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_equipment(db, status=None)
    headers = ["编码", "名称", "型号", "车间", "状态", "采购日期", "最后保养日期"]
    rows = [[i.code, i.name, i.model or "", i.workshop or "", i.status, str(i.purchase_date or ""), str(i.last_maintenance_date or "")] for i in items]
    return make_excel_response(headers, rows, "equipment.xlsx", "设备")


@router.post("")
def create_equipment_api(
    payload: EquipmentCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    eq_code = resolve_code(
        db,
        biz_type=BizType.EQUIPMENT,
        code=payload.code,
        exists=lambda c: _equipment_code_exists(db, c),
        duplicate_msg="设备编码已存在",
    )
    e = create_equipment(
        db,
        code=eq_code,
        name=payload.name,
        model=payload.model,
        workshop=payload.workshop,
        remark=payload.remark,
    )
    db.commit()
    return ok({"id": e.id, "code": e.code, "name": e.name})


@router.put("/{equipment_id}")
def update_equipment_api(
    equipment_id: int,
    payload: EquipmentUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    eq = get_equipment_by_id(db, equipment_id)
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    if payload.code and payload.code != eq.code and _equipment_code_exists(db, payload.code):
        raise HTTPException(status_code=400, detail="设备编码已存在")
    update_equipment(
        db,
        item=eq,
        code=payload.code,
        name=payload.name,
        model=payload.model,
        workshop=payload.workshop,
        status=payload.status,
        purchase_date=payload.purchase_date,
        last_maintenance_date=payload.last_maintenance_date,
        next_maintenance_date=payload.next_maintenance_date,
        maintenance_interval_days=payload.maintenance_interval_days,
        remark=payload.remark,
    )
    db.commit()
    return ok({"id": eq.id, "code": eq.code, "name": eq.name})


# ==================== 设备巡检 ====================

@router.post("/{equipment_id}/check")
def check_equipment_api(
    equipment_id: int,
    check_type: str = Query(default="daily"),
    result: str = Query(default="ok"),
    description: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    eq = get_equipment_by_id(db, equipment_id)
    if not eq:
        raise HTTPException(status_code=400, detail="设备不存在")
    ck = create_equipment_check(
        db,
        equipment_id=equipment_id,
        check_type=check_type,
        result=result,
        description=description,
        checked_by=user.id,
    )
    db.commit()
    return ok({"id": ck.id, "equipment_id": ck.equipment_id, "result": ck.result})


@router.get("/{equipment_id}/checks")
def list_checks_api(
    equipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_equipment_checks(db, equipment_id)
    return ok({"items": [{"id": c.id, "check_type": c.check_type, "result": c.result,
            "description": c.description, "checked_by": c.checked_by, "created_at": c.created_at} for c in items]})


# ==================== 设备保养计划 ====================

@router.get("/maintenance-plans")
def list_maintenance_plans_api(
    equipment_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_equipment_maintenance_plans(db, equipment_id=equipment_id)
    return ok({"items": [
        {"id": p.id, "equipment_id": p.equipment_id, "plan_type": p.plan_type,
         "check_items": p.check_items, "interval_days": p.interval_days,
         "responsible_user_id": p.responsible_user_id, "next_date": str(p.next_date) if p.next_date else None,
         "remark": p.remark, "created_at": p.created_at, "updated_at": p.updated_at}
        for p in items
    ]})


@router.post("/maintenance-plans")
def create_maintenance_plan_api(
    payload: EquipmentMaintenancePlanCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 校验设备是否存在
    eq = get_equipment_by_id(db, payload.equipment_id)
    if not eq:
        raise HTTPException(status_code=400, detail="设备不存在")
    p = create_equipment_maintenance_plan(
        db,
        equipment_id=payload.equipment_id,
        plan_type=payload.plan_type,
        check_items=payload.check_items,
        interval_days=payload.interval_days,
        responsible_user_id=payload.responsible_user_id,
        next_date=payload.next_date,
        remark=payload.remark,
    )
    db.commit()
    return ok({"id": p.id, "equipment_id": p.equipment_id, "plan_type": p.plan_type})


@router.put("/maintenance-plans/{plan_id}")
def update_maintenance_plan_api(
    plan_id: int,
    payload: EquipmentMaintenancePlanUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = get_equipment_maintenance_plans(db, plan_id)
    if not p:
        raise HTTPException(status_code=400, detail="保养计划不存在")
    update_equipment_maintenance_plan(
        db,
        item=p,
        equipment_id=payload.equipment_id,
        plan_type=payload.plan_type,
        check_items=payload.check_items,
        interval_days=payload.interval_days,
        responsible_user_id=payload.responsible_user_id,
        next_date=payload.next_date,
        remark=payload.remark,
    )
    db.commit()
    return ok({"id": p.id})


@router.delete("/maintenance-plans/{plan_id}")
def delete_maintenance_plan_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = get_equipment_maintenance_plans(db, plan_id)
    if not p:
        raise HTTPException(status_code=400, detail="保养计划不存在")
    delete_equipment_maintenance_plan(db, p)
    db.commit()
    return ok({"id": plan_id})


# ==================== 设备保养日志 ====================

@router.get("/maintenance-logs")
def list_maintenance_logs_api(
    equipment_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_equipment_maintenance_logs(db, equipment_id=equipment_id)
    return ok({"items": [
        {"id": l.id, "plan_id": l.plan_id, "equipment_id": l.equipment_id,
         "check_result": l.check_result, "description": l.description,
         "attachments": l.attachments, "checked_by": l.checked_by, "created_at": l.created_at}
        for l in items
    ]})


@router.post("/maintenance-logs")
def create_maintenance_log_api(
    payload: EquipmentMaintenanceLogCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 校验设备是否存在
    eq = get_equipment_by_id(db, payload.equipment_id)
    if not eq:
        raise HTTPException(status_code=400, detail="设备不存在")
    log = create_equipment_maintenance_log(
        db,
        equipment_id=payload.equipment_id,
        check_result=payload.check_result,
        plan_id=payload.plan_id,
        description=payload.description,
        attachments=payload.attachments,
        checked_by=user.id,
    )
    db.commit()
    return ok({"id": log.id, "equipment_id": log.equipment_id, "check_result": log.check_result})
