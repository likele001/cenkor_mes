import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.material_bom import get_effective_bom_map_by_sku_ids
from app.crud.kanban import get_orders_progress_map
from app.crud.order import get_order_by_id, list_orders, order_has_work_orders
from app.crud.purchase_order import create_purchase_order
from app.crud.production_plan import (
    create_plan,
    get_plan_by_code,
    get_plan_by_id,
    get_plan_with_order_info,
    list_plans_with_order_info,
    ensure_plan_released_for_dispatch,
    plan_is_released,
    release_plan,
    update_plan)
from app.crud.production_calendar import delete_calendar_day, get_calendar_day, list_calendar_days, upsert_calendar_day
from app.crud.task_assignment import replace_task_assignments, task_has_assignments
from app.crud.tenant_setting import get_setting, upsert_setting
from app.crud.warehouse import sum_stock_qty_by_sku_ids
from app.models.plan_purchase_link import PlanPurchaseLink
from app.models.order import OrderItem
from app.models.process import Process
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.material import Supplier
from app.models.production_plan import ProductionPlan
from app.models.sku import Sku
from app.models.task import Task
from app.models.equipment import Equipment
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.production_plan import (
    AutoDispatchIn,
    CalendarDayUpsertIn,
    EquipmentCapacitiesIn,
    ProductionPlanCreateIn,
    ProductionPlanReleaseIn,
    ProductionPlanUpdateIn,
    UserCapacitiesIn,
    WorkshopCapacitiesIn)
from app.services.dispatch_candidates import (
    build_user_department_map,
    build_user_skill_map,
    filter_candidates_for_task,
    list_dispatch_candidate_users)
from app.services.dispatch_proficiency import user_process_proficiency_map
from app.services.plan_capacity_settings import (
    KEY_MINUTES,
    get_capacity_meta,
    get_capacity_unit,
    get_default_capacity,
    get_equipment_capacity_map,
    get_user_capacity_map,
    get_workshop_capacity_map,
    save_capacity_unit,
    task_load_qty)
from app.crud.process_skill import get_process_skills_map

router = APIRouter(dependencies=[Depends(require_permissions(["plan.manage"]))])

def _out(
    plan,
    order_code: str | None,
    customer_name: str | None,
    qty: int | None,
    *,
    has_work_orders: bool = False,
    order_status: str | None = None,
    done_qty: int = 0,
    progress: float | None = None) -> dict:
    released = plan_is_released(plan)
    plan_qty = int(qty or 0)
    done = int(done_qty or 0)
    if progress is not None:
        pct = round(float(progress) * 100, 2)
    elif plan_qty > 0:
        pct = round(done / plan_qty * 100, 2)
    else:
        pct = 0.0
    return {
        "id": plan.id,
        "order_id": plan.order_id,
        "code": plan.code,
        "status": plan.status,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "work_days": plan.work_days,
        "remark": plan.remark,
        "created_by": plan.created_by,
        "released_at": getattr(plan, "released_at", None),
        "released_by": getattr(plan, "released_by", None),
        "can_release": plan.status == "planned" and not released and not has_work_orders,
        "has_work_orders": has_work_orders,
        "order_status": order_status,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "order_code": order_code,
        "customer_name": customer_name,
        "qty": plan_qty,
        "done_qty": done,
        "progress": pct,
    }

_CAPACITY_KEY_MINUTES = "plan.capacity.minutes_per_day"
_CAPACITY_KEY_LEGACY = "plan.capacity.per_day"
_CAPACITY_KEY_WORKSHOPS = "plan.capacity.workshops.minutes_per_day"
_CAPACITY_KEY_USERS = "plan.capacity.users.minutes_per_day"
_CAPACITY_KEY_EQUIPMENTS = "plan.capacity.equipments.minutes_per_day"
_CAL_WORKDAYS_KEY = "plan.calendar.workdays"
_CAL_DEFAULT_WORKDAYS = [1, 2, 3, 4, 5, 6]

def _get_workdays_setting(db: Session) -> list[int]:
    it = get_setting(db, key=_CAL_WORKDAYS_KEY)
    if not it or not it.value:
        return list(_CAL_DEFAULT_WORKDAYS)
    try:
        v = json.loads(it.value)
        if not isinstance(v, list):
            return list(_CAL_DEFAULT_WORKDAYS)
        out = []
        for x in v:
            try:
                n = int(x)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= 7:
                out.append(n)
        return out or list(_CAL_DEFAULT_WORKDAYS)
    except json.JSONDecodeError:
        return list(_CAL_DEFAULT_WORKDAYS)

def _get_default_capacity_minutes(db: Session) -> int:
    return get_default_capacity(db)

def _get_workshop_capacity_map(db: Session) -> dict[str, int]:
    return get_workshop_capacity_map(db)

def _get_user_capacity_map(db: Session) -> dict[int, int]:
    return get_user_capacity_map(db)

def _get_equipment_capacity_map(db: Session) -> dict[int, int]:
    return get_equipment_capacity_map(db)

def _calendar_map(db: Session, date_from: date, date_to: date):
    rows = list_calendar_days(db, date_from=date_from, date_to=date_to)
    return {it.day: it for it in rows}

def _is_workday(day0: date, *, workdays: list[int], cal_map) -> bool:
    it = cal_map.get(day0)
    if it is not None:
        return bool(it.is_workday)
    return int(day0.isoweekday()) in workdays

def _capacity_minutes_for_day(day0: date, *, is_workday: bool, default_capacity: int, cal_map) -> int:
    if not is_workday:
        return 0
    it = cal_map.get(day0)
    if it is not None and it.capacity_minutes is not None and int(it.capacity_minutes) > 0:
        return int(it.capacity_minutes)
    return int(default_capacity)

@router.get("/plans/capacity")
def get_capacity_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    return ok(get_capacity_meta(db))

@router.put("/plans/capacity/unit")
def set_capacity_unit_api(
    unit: str = Query(description="pieces=件/天, minutes=分钟/天"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    saved = save_capacity_unit(db, unit=unit)
    db.commit()
    meta = get_capacity_meta(db)
    return ok(meta)

@router.put("/plans/capacity")
def set_capacity_api(
    capacity: int = Query(ge=1, le=10000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    upsert_setting(db, key=KEY_MINUTES, value=str(int(capacity)))
    db.commit()
    return ok(get_capacity_meta(db))

@router.get("/plans/capacity/workshops")
def get_workshop_capacity_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    default_capacity = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)
    mp = _get_workshop_capacity_map(db)
    items = [{"workshop": k, "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": items, "default_capacity": default_capacity, "unit": unit})

@router.put("/plans/capacity/workshops")
def set_workshop_capacity_api(
    payload: WorkshopCapacitiesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = payload.items or []
    mp = {}
    for it in items:
        k = str(it.workshop or "").strip()
        if not k:
            continue
        mp[k[:64]] = int(it.capacity_minutes)
    upsert_setting(db, key=_CAPACITY_KEY_WORKSHOPS, value=json.dumps(mp, ensure_ascii=False))
    db.commit()
    out = [{"workshop": k, "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": out})

@router.get("/plans/capacity/users")
def get_user_capacity_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    default_capacity = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)
    mp = _get_user_capacity_map(db)
    items = [{"user_id": int(k), "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": items, "default_capacity": default_capacity, "unit": unit})

@router.get("/plans/capacity/user-rows")
def list_user_capacity_rows_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """人员产能配置行：仅「员工」角色（与自动派工候选人一致）。"""
    default_capacity = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)
    user_caps = _get_user_capacity_map(db)
    workers = list_dispatch_candidate_users(db, include_leader=False, limit=500)
    items = [
        {
            "user_id": int(u.id),
            "name": (u.full_name or u.username or str(u.id)),
            "capacity_minutes": int(user_caps.get(int(u.id)) or 0),
        }
        for u in workers
    ]
    items.sort(key=lambda x: str(x["name"]))
    return ok({"items": items, "default_capacity": default_capacity, "unit": unit})

@router.put("/plans/capacity/users")
def set_user_capacity_api(
    payload: UserCapacitiesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = payload.items or []
    allowed_ids = {
        int(u.id)
        for u in list_dispatch_candidate_users(db, include_leader=False, limit=500)
    }
    mp: dict[int, int] = {}
    for it in items:
        uid = int(it.user_id)
        if uid <= 0 or uid not in allowed_ids:
            continue
        mp[uid] = int(it.capacity_minutes)
    upsert_setting(db, key=_CAPACITY_KEY_USERS, value=json.dumps(mp, ensure_ascii=False))
    db.commit()
    out = [{"user_id": int(k), "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": out})

@router.get("/plans/capacity/equipments")
def get_equipment_capacity_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    default_capacity = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)
    mp = _get_equipment_capacity_map(db)
    items = [{"equipment_id": int(k), "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": items, "default_capacity": default_capacity, "unit": unit})

@router.put("/plans/capacity/equipments")
def set_equipment_capacity_api(
    payload: EquipmentCapacitiesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = payload.items or []
    mp: dict[int, int] = {}
    for it in items:
        mp[int(it.equipment_id)] = min(int(it.capacity_minutes), 10000)
    upsert_setting(db, key=_CAPACITY_KEY_EQUIPMENTS, value=json.dumps(mp, ensure_ascii=False))
    db.commit()
    out = [{"equipment_id": int(k), "capacity_minutes": int(v)} for k, v in sorted(mp.items(), key=lambda x: x[0])]
    return ok({"items": out})

@router.get("/plans/calendar")
def list_calendar_api(
    date_from: date = Query(),
    date_to: date = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to 不能早于 date_from")
    days = (date_to - date_from).days + 1
    if days > 370:
        raise HTTPException(status_code=400, detail="日期范围过大")

    workdays = _get_workdays_setting(db)
    default_capacity = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)

    rows = list_calendar_days(db, date_from=date_from, date_to=date_to)
    items = [
        {
            "day": it.day.isoformat(),
            "is_workday": bool(it.is_workday),
            "capacity_minutes": int(it.capacity_minutes) if it.capacity_minutes is not None else None,
            "remark": it.remark,
        }
        for it in rows
    ]
    return ok({"items": items, "default_workdays": workdays, "default_capacity": default_capacity, "unit": unit})

@router.put("/plans/calendar/day")
def upsert_calendar_day_api(
    payload: CalendarDayUpsertIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    cap = payload.capacity_minutes
    if not payload.is_workday:
        cap = None
    if cap is not None and int(cap) <= 0:
        cap = None

    it = upsert_calendar_day(
        db,
        day=payload.day,
        is_workday=bool(payload.is_workday),
        capacity_minutes=int(cap) if cap is not None else None,
        remark=payload.remark)
    db.commit()
    return ok(
        {
            "day": it.day.isoformat(),
            "is_workday": bool(it.is_workday),
            "capacity_minutes": int(it.capacity_minutes) if it.capacity_minutes is not None else None,
            "remark": it.remark,
        }
    )

@router.delete("/plans/calendar/day")
def delete_calendar_day_api(
    day: date = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    deleted = delete_calendar_day(db, day=day)
    db.commit()
    return ok({"deleted": bool(deleted)})

@router.get("/plans/load")
def load_api(
    date_from: date = Query(),
    date_to: date = Query(),
    capacity: int | None = Query(default=None, ge=1, le=10000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to 不能早于 date_from")
    days = (date_to - date_from).days + 1
    if days > 370:
        raise HTTPException(status_code=400, detail="日期范围过大")

    qty_sum_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty).label("qty"))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    tasks_minutes_sq = (
        select(
            WorkOrder.order_id.label("order_id"),
            func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
        .select_from(WorkOrder)
        .join(Task, and_(Task.work_order_id == WorkOrder.id))
        .join(Process, and_(Process.id == Task.process_id))
        .group_by(WorkOrder.order_id)
        .subquery()
    )

    route_minutes_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
        .select_from(OrderItem)
        .join(Sku, and_(Sku.id == OrderItem.sku_id))
        .join(
            ProcessRoute,
            and_(
                ProcessRoute.product_id == Sku.product_id,
                ProcessRoute.is_default.is_(True),
                ProcessRoute.is_active.is_(True)))
        .join(ProcessRouteStep, and_(ProcessRouteStep.route_id == ProcessRoute.id))
        .join(Process, and_(Process.id == ProcessRouteStep.process_id))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    total_minutes_expr = func.coalesce(tasks_minutes_sq.c.minutes, route_minutes_sq.c.minutes, 0)

    rows = db.execute(
        select(
            ProductionPlan,
            func.coalesce(qty_sum_sq.c.qty, 0).label("qty"),
            total_minutes_expr.label("total_minutes"))
        .outerjoin(qty_sum_sq, qty_sum_sq.c.order_id == ProductionPlan.order_id)
        .outerjoin(tasks_minutes_sq, tasks_minutes_sq.c.order_id == ProductionPlan.order_id)
        .outerjoin(route_minutes_sq, route_minutes_sq.c.order_id == ProductionPlan.order_id)
        .where(ProductionPlan.status.in_(["planned", "in_progress"]),
            ProductionPlan.start_date.is_not(None),
            ProductionPlan.end_date.is_not(None),
            ProductionPlan.start_date <= date_to,
            ProductionPlan.end_date >= date_from)
        .order_by(ProductionPlan.id.desc())
    ).all()

    cap = capacity
    if cap is None:
        cap = _get_default_capacity_minutes(db)
    if cap <= 0:
        cap = 300 if get_capacity_unit(db) == "pieces" else 480

    unit = get_capacity_unit(db)
    workdays = _get_workdays_setting(db)
    cal_map = _calendar_map(db, date_from=date_from, date_to=date_to)

    count_by_day: dict[date, float] = {date_from + timedelta(days=i): 0.0 for i in range(days)}
    for p, qty, total_minutes in rows:
        s = p.start_date
        e = p.end_date
        if not s or not e:
            continue
        span = int(p.work_days or 0)
        if span <= 0:
            cur = s
            span = 0
            while cur <= e:
                if _is_workday(cur, workdays=workdays, cal_map=cal_map):
                    span += 1
                cur += timedelta(days=1)
        if span > 0:
            cal_span = 0
            cur2 = s
            while cur2 <= e:
                if _is_workday(cur2, workdays=workdays, cal_map=cal_map):
                    cal_span += 1
                cur2 += timedelta(days=1)
            if cal_span > 0 and span > cal_span:
                span = cal_span
        if span <= 0:
            span = (e - s).days + 1
        if span <= 0:
            span = 1
        if unit == "pieces":
            daily_load = float(qty or 0) / float(span)
        else:
            daily_load = float(total_minutes or 0) / float(span)
            if daily_load <= 0:
                daily_load = float(qty or 0) / float(span)

        if s < date_from:
            s = date_from
        if e > date_to:
            e = date_to
        cur = s
        while cur <= e:
            if cur in count_by_day and _is_workday(cur, workdays=workdays, cal_map=cal_map):
                count_by_day[cur] += daily_load
            cur += timedelta(days=1)

    items = []
    for d, c in count_by_day.items():
        is_workday = _is_workday(d, workdays=workdays, cal_map=cal_map)
        cap_day = _capacity_minutes_for_day(d, is_workday=is_workday, default_capacity=int(cap), cal_map=cal_map)
        items.append(
            {
                "date": d.isoformat(),
                "count": round(float(c), 2),
                "capacity": cap_day,
                "is_workday": bool(is_workday),
                "overload": bool(cap_day > 0 and float(c) > float(cap_day)),
            }
        )
    return ok({"items": items, "capacity": cap, "metric": unit, "default_workdays": workdays})

@router.get("/plans/load/detail")
def load_detail_api(
    day: date = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    default_capacity = _get_default_capacity_minutes(db)

    workdays = _get_workdays_setting(db)
    cal_day_map = _calendar_map(db, date_from=day, date_to=day)
    is_workday = _is_workday(day, workdays=workdays, cal_map=cal_day_map)
    cap_day = _capacity_minutes_for_day(day, is_workday=is_workday, default_capacity=int(default_capacity), cal_map=cal_day_map)
    if not is_workday:
        return ok({"day": day.isoformat(), "items": [], "metric": "minutes", "is_workday": False, "capacity": cap_day, "workshops": [], "users": [], "equipments": []})

    qty_sum_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty).label("qty"))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    tasks_minutes_sq = (
        select(
            WorkOrder.order_id.label("order_id"),
            func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
        .select_from(WorkOrder)
        .join(Task, and_(Task.work_order_id == WorkOrder.id))
        .join(Process, and_(Process.id == Task.process_id))
        .group_by(WorkOrder.order_id)
        .subquery()
    )

    route_minutes_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
        .select_from(OrderItem)
        .join(Sku, and_(Sku.id == OrderItem.sku_id))
        .join(
            ProcessRoute,
            and_(
                ProcessRoute.product_id == Sku.product_id,
                ProcessRoute.is_default.is_(True),
                ProcessRoute.is_active.is_(True)))
        .join(ProcessRouteStep, and_(ProcessRouteStep.route_id == ProcessRoute.id))
        .join(Process, and_(Process.id == ProcessRouteStep.process_id))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    total_minutes_expr = func.coalesce(tasks_minutes_sq.c.minutes, route_minutes_sq.c.minutes, 0)

    rows = db.execute(
        select(
            ProductionPlan,
            func.coalesce(qty_sum_sq.c.qty, 0).label("qty"),
            total_minutes_expr.label("total_minutes"),
            func.coalesce(func.sum(PurchaseOrderItem.received_qty), 0).label("received_qty"),
            func.coalesce(func.sum(PurchaseOrderItem.qty), 0).label("total_qty"))
        .outerjoin(qty_sum_sq, qty_sum_sq.c.order_id == ProductionPlan.order_id)
        .outerjoin(tasks_minutes_sq, tasks_minutes_sq.c.order_id == ProductionPlan.order_id)
        .outerjoin(route_minutes_sq, route_minutes_sq.c.order_id == ProductionPlan.order_id)
        .outerjoin(PlanPurchaseLink, (PlanPurchaseLink.plan_id == ProductionPlan.id))
        .outerjoin(PurchaseOrder, (PurchaseOrder.id == PlanPurchaseLink.purchase_order_id))
        .outerjoin(PurchaseOrderItem, (PurchaseOrderItem.order_id == PurchaseOrder.id))
        .where(ProductionPlan.status.in_(["planned", "in_progress"]),
            ProductionPlan.start_date.is_not(None),
            ProductionPlan.end_date.is_not(None),
            ProductionPlan.start_date <= day,
            ProductionPlan.end_date >= day)
        .group_by(ProductionPlan.id, qty_sum_sq.c.qty, tasks_minutes_sq.c.minutes, route_minutes_sq.c.minutes)
        .order_by(ProductionPlan.id.desc())
    ).all()

    min_s = None
    max_e = None
    for p, _, _, _, _ in rows:
        if p.start_date and (min_s is None or p.start_date < min_s):
            min_s = p.start_date
        if p.end_date and (max_e is None or p.end_date > max_e):
            max_e = p.end_date
    if min_s is None:
        min_s = day
    if max_e is None:
        max_e = day
    cal_map = _calendar_map(db, date_from=min_s, date_to=max_e)

    items = []
    for p, qty, total_minutes, received_qty, total_qty in rows:
        s = p.start_date
        e = p.end_date
        span = int(p.work_days or 0)
        if span <= 0 and s and e:
            cur = s
            span = 0
            while cur <= e:
                if _is_workday(cur, workdays=workdays, cal_map=cal_map):
                    span += 1
                cur += timedelta(days=1)
        if span > 0 and s and e:
            cal_span = 0
            cur2 = s
            while cur2 <= e:
                if _is_workday(cur2, workdays=workdays, cal_map=cal_map):
                    cal_span += 1
                cur2 += timedelta(days=1)
            if cal_span > 0 and span > cal_span:
                span = cal_span
        if span <= 0 and s and e:
            span = (e - s).days + 1
        if span <= 0:
            span = 1
        daily_minutes = float(total_minutes or 0) / float(span)
        if daily_minutes <= 0:
            daily_minutes = float(qty or 0) / float(span)
        items.append(
            {
                "id": p.id,
                "code": p.code,
                "order_id": p.order_id,
                "status": p.status,
                "start_date": p.start_date,
                "end_date": p.end_date,
                "work_days": p.work_days,
                "remark": p.remark,
                "qty": int(qty or 0),
                "total_minutes": int(total_minutes or 0),
                "daily_minutes": round(daily_minutes, 2),
                "purchase_received_qty": int(received_qty or 0),
                "purchase_total_qty": int(total_qty or 0),
            }
        )

    order_ids = [int(p.order_id) for p, _, _, _, _ in rows if p.order_id]
    workshop_load: dict[str, float] = {}
    if order_ids:
        w_col = func.coalesce(Process.workshop, "未分车间").label("workshop")

        tasks_ws_rows = db.execute(
            select(
                WorkOrder.order_id.label("order_id"),
                w_col,
                func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
            .select_from(WorkOrder)
            .join(Task, and_(Task.work_order_id == WorkOrder.id))
            .join(Process, and_(Process.id == Task.process_id))
            .where(WorkOrder.order_id.in_(order_ids))
            .group_by(WorkOrder.order_id, w_col)
        ).all()

        route_ws_rows = db.execute(
            select(
                OrderItem.order_id.label("order_id"),
                w_col,
                func.sum(OrderItem.qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
            .select_from(OrderItem)
            .join(Sku, and_(Sku.id == OrderItem.sku_id))
            .join(
                ProcessRoute,
                and_(
                    ProcessRoute.product_id == Sku.product_id,
                    ProcessRoute.is_default.is_(True),
                    ProcessRoute.is_active.is_(True)))
            .join(ProcessRouteStep, and_(ProcessRouteStep.route_id == ProcessRoute.id))
            .join(Process, and_(Process.id == ProcessRouteStep.process_id))
            .where(OrderItem.order_id.in_(order_ids))
            .group_by(OrderItem.order_id, w_col)
        ).all()

        tasks_ws: dict[int, dict[str, int]] = {}
        for oid, ws, mins in tasks_ws_rows:
            tasks_ws.setdefault(int(oid), {})[str(ws or "未分车间")] = int(mins or 0)
        route_ws: dict[int, dict[str, int]] = {}
        for oid, ws, mins in route_ws_rows:
            route_ws.setdefault(int(oid), {})[str(ws or "未分车间")] = int(mins or 0)

        workshop_caps = _get_workshop_capacity_map(db)

        for p, qty, total_minutes, _, _ in rows:
            s = p.start_date
            e = p.end_date
            if not s or not e:
                continue
            span = int(p.work_days or 0)
            if span <= 0:
                cur = s
                span = 0
                while cur <= e:
                    if _is_workday(cur, workdays=workdays, cal_map=cal_map):
                        span += 1
                    cur += timedelta(days=1)
            if span > 0:
                cal_span = 0
                cur2 = s
                while cur2 <= e:
                    if _is_workday(cur2, workdays=workdays, cal_map=cal_map):
                        cal_span += 1
                    cur2 += timedelta(days=1)
                if cal_span > 0 and span > cal_span:
                    span = cal_span
            if span <= 0:
                span = 1

            oid = int(p.order_id)
            src = tasks_ws.get(oid) or {}
            src_total = sum(int(x or 0) for x in src.values())
            if src_total <= 0:
                src = route_ws.get(oid) or {}
                src_total = sum(int(x or 0) for x in src.values())
            if src_total <= 0:
                if total_minutes and float(total_minutes) > 0:
                    src = {"未分车间": int(total_minutes or 0)}
                else:
                    src = {"未分车间": int(qty or 0)}

            for ws, mins in src.items():
                if int(mins or 0) <= 0:
                    continue
                workshop_load[ws] = workshop_load.get(ws, 0.0) + float(mins) / float(span)

    workshops = []
    if workshop_load:
        workshop_caps = _get_workshop_capacity_map(db)
        for ws, mins in sorted(workshop_load.items(), key=lambda x: x[1], reverse=True):
            cap_ws = int(workshop_caps.get(ws) or default_capacity)
            workshops.append(
                {
                    "workshop": ws,
                    "minutes": round(float(mins), 2),
                    "capacity": cap_ws,
                    "overload": bool(cap_ws > 0 and float(mins) > float(cap_ws)),
                }
            )

    user_load: dict[int, float] = {}
    if order_ids:
        tasks_user_rows = db.execute(
            select(
                WorkOrder.order_id.label("order_id"),
                Task.assigned_user_id.label("assigned_user_id"),
                func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
            .select_from(WorkOrder)
            .join(Task, and_(Task.work_order_id == WorkOrder.id))
            .join(Process, and_(Process.id == Task.process_id))
            .where(WorkOrder.order_id.in_(order_ids))
            .group_by(WorkOrder.order_id, Task.assigned_user_id)
        ).all()

        tasks_by_user: dict[int, dict[int, int]] = {}
        for oid, uid, mins in tasks_user_rows:
            tasks_by_user.setdefault(int(oid), {})[int(uid or 0)] = int(mins or 0)

        for p, qty, total_minutes, _, _ in rows:
            s = p.start_date
            e = p.end_date
            if not s or not e:
                continue
            span = int(p.work_days or 0)
            if span <= 0:
                cur = s
                span = 0
                while cur <= e:
                    if _is_workday(cur, workdays=workdays, cal_map=cal_map):
                        span += 1
                    cur += timedelta(days=1)
            if span > 0:
                cal_span = 0
                cur2 = s
                while cur2 <= e:
                    if _is_workday(cur2, workdays=workdays, cal_map=cal_map):
                        cal_span += 1
                    cur2 += timedelta(days=1)
                if cal_span > 0 and span > cal_span:
                    span = cal_span
            if span <= 0:
                span = 1

            oid = int(p.order_id)
            src = tasks_by_user.get(oid) or {}
            src_total = sum(int(x or 0) for x in src.values())
            if src_total <= 0:
                if total_minutes and float(total_minutes) > 0:
                    src = {0: int(total_minutes or 0)}
                else:
                    src = {0: int(qty or 0)}

            for uid, mins in src.items():
                if int(mins or 0) <= 0:
                    continue
                user_load[int(uid)] = user_load.get(int(uid), 0.0) + float(mins) / float(span)

    users = []
    if user_load:
        caps = _get_user_capacity_map(db)
        user_ids = [uid for uid in user_load.keys() if uid > 0]
        user_map = {}
        if user_ids:
            for uid, username, full_name in db.execute(
                select(User.id, User.username, User.full_name).where(User.id.in_(user_ids))
            ).all():
                user_map[int(uid)] = {"username": username, "full_name": full_name}

        for uid, mins in sorted(user_load.items(), key=lambda x: x[1], reverse=True):
            cap_u = int(caps.get(uid) or default_capacity)
            if uid <= 0:
                users.append({"user_id": 0, "name": "未派工", "minutes": round(float(mins), 2), "capacity": cap_u, "overload": bool(cap_u > 0 and float(mins) > float(cap_u))})
                continue
            info = user_map.get(uid) or {}
            name = info.get("full_name") or info.get("username") or str(uid)
            users.append({"user_id": int(uid), "name": name, "minutes": round(float(mins), 2), "capacity": cap_u, "overload": bool(cap_u > 0 and float(mins) > float(cap_u))})

    equipment_load: dict[int, float] = {}
    if order_ids:
        tasks_eq_rows = db.execute(
            select(
                WorkOrder.order_id.label("order_id"),
                Task.equipment_id.label("equipment_id"),
                func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 0)).label("minutes"))
            .select_from(WorkOrder)
            .join(Task, and_(Task.work_order_id == WorkOrder.id))
            .join(Process, and_(Process.id == Task.process_id))
            .where(WorkOrder.order_id.in_(order_ids))
            .group_by(WorkOrder.order_id, Task.equipment_id)
        ).all()

        tasks_by_eq: dict[int, dict[int, int]] = {}
        for oid, eid, mins in tasks_eq_rows:
            tasks_by_eq.setdefault(int(oid), {})[int(eid or 0)] = int(mins or 0)

        for p, qty, total_minutes, _, _ in rows:
            s = p.start_date
            e = p.end_date
            if not s or not e:
                continue
            span = int(p.work_days or 0)
            if span <= 0:
                cur = s
                span = 0
                while cur <= e:
                    if _is_workday(cur, workdays=workdays, cal_map=cal_map):
                        span += 1
                    cur += timedelta(days=1)
            if span > 0:
                cal_span = 0
                cur2 = s
                while cur2 <= e:
                    if _is_workday(cur2, workdays=workdays, cal_map=cal_map):
                        cal_span += 1
                    cur2 += timedelta(days=1)
                if cal_span > 0 and span > cal_span:
                    span = cal_span
            if span <= 0:
                span = 1

            oid = int(p.order_id)
            src = tasks_by_eq.get(oid) or {}
            src_total = sum(int(x or 0) for x in src.values())
            if src_total <= 0:
                if total_minutes and float(total_minutes) > 0:
                    src = {0: int(total_minutes or 0)}
                else:
                    src = {0: int(qty or 0)}

            for eid, mins in src.items():
                if int(mins or 0) <= 0:
                    continue
                equipment_load[int(eid)] = equipment_load.get(int(eid), 0.0) + float(mins) / float(span)

    equipments = []
    if equipment_load:
        caps = _get_equipment_capacity_map(db)
        eq_ids = [eid for eid in equipment_load.keys() if eid > 0]
        eq_map = {}
        if eq_ids:
            for eid, code, name in db.execute(
                select(Equipment.id, Equipment.code, Equipment.name).where(Equipment.id.in_(eq_ids))
            ).all():
                eq_map[int(eid)] = {"code": code, "name": name}

        for eid, mins in sorted(equipment_load.items(), key=lambda x: x[1], reverse=True):
            cap_e = int(caps.get(eid) or default_capacity)
            if eid <= 0:
                equipments.append(
                    {"equipment_id": 0, "name": "未指定设备", "minutes": round(float(mins), 2), "capacity": cap_e, "overload": bool(cap_e > 0 and float(mins) > float(cap_e))}
                )
                continue
            info = eq_map.get(eid) or {}
            name = (info.get("code") or str(eid)) + " " + (info.get("name") or "")
            equipments.append(
                {"equipment_id": int(eid), "name": name.strip(), "minutes": round(float(mins), 2), "capacity": cap_e, "overload": bool(cap_e > 0 and float(mins) > float(cap_e))}
            )

    return ok(
        {
            "day": day.isoformat(),
            "items": items,
            "metric": "minutes",
            "is_workday": True,
            "capacity": cap_day,
            "workshops": workshops,
            "users": users,
            "equipments": equipments,
        }
    )

@router.post("/plans/{plan_id}/auto-schedule")
def auto_schedule_api(
    plan_id: int,
    mode: str = Query(default="backward", description="backward/forward"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    plan, order_code, order_status, customer_name, qty = row
    order = get_order_by_id(db, order_id=plan.order_id, with_items=False)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")

    if mode not in ["backward", "forward"]:
        raise HTTPException(status_code=400, detail="mode 参数错误")

    start = plan.start_date
    end = plan.end_date

    workdays = _get_workdays_setting(db)

    def is_workday_db(d: date) -> bool:
        it = get_calendar_day(db, day=d)
        if it is not None:
            return bool(it.is_workday)
        return int(d.isoweekday()) in workdays

    def normalize_to_workday(d: date, *, direction: int) -> date:
        cur = d
        for _ in range(400):
            if is_workday_db(cur):
                return cur
            cur = cur + timedelta(days=direction)
        return d

    def shift_workdays(d: date, delta_workdays: int) -> date:
        if delta_workdays == 0:
            return d
        step = 1 if delta_workdays > 0 else -1
        remain = abs(int(delta_workdays))
        cur = d
        while remain > 0:
            cur = cur + timedelta(days=step)
            cur = normalize_to_workday(cur, direction=step)
            remain -= 1
        return cur

    work_days = plan.work_days
    if work_days is None or work_days <= 0:
        if start and end:
            work_days = (end - start).days + 1
        else:
            work_days = 1

    if mode == "backward":
        if not end:
            end = order.due_date
        if not end:
            raise HTTPException(status_code=400, detail="缺少结束日期，且订单未设置交期")
        end = normalize_to_workday(end, direction=-1)
        start = shift_workdays(end, -(int(work_days) - 1))
    else:
        if not start:
            raise HTTPException(status_code=400, detail="缺少开始日期，无法正排")
        start = normalize_to_workday(start, direction=1)
        end = shift_workdays(start, int(work_days) - 1)

    update_plan(db, plan=plan, start_date=start, end_date=end, work_days=int(work_days))
    db.commit()
    wo_flag = order_has_work_orders(db, order_id=plan.order_id)
    return ok(_out(plan, order_code, customer_name, qty, has_work_orders=wo_flag, order_status=order_status))

@router.post("/plans/{plan_id}/auto-dispatch")
def auto_dispatch_api(
    plan_id: int,
    payload: AutoDispatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    plan, _, _, _, _ = row
    try:
        release_info = ensure_plan_released_for_dispatch(
            db,
            plan=plan,
            releaser_user_id=user.id,
            auto_release=payload.auto_release,
            allow_shortage=payload.allow_shortage)
        if release_info is not None:
            db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    plan, _, _, _, _ = row
    if plan.status == "planned":
        raise HTTPException(
            status_code=400,
            detail=(
                "生产计划尚未「确认下发」。订单「审核通过」不等于计划已下发，"
                "请在【生产计划】列表点击「确认下发」后再派工。"
            ))
    if not plan.start_date or not plan.end_date:
        raise HTTPException(status_code=400, detail="请先设置计划开始/结束日期")

    workdays = _get_workdays_setting(db)
    cal_map = _calendar_map(db, date_from=plan.start_date, date_to=plan.end_date)
    span = 0
    cur = plan.start_date
    while cur <= plan.end_date:
        if _is_workday(cur, workdays=workdays, cal_map=cal_map):
            span += 1
        cur += timedelta(days=1)
    if span <= 0:
        span = 1

    user_ids = payload.user_ids
    workers = list_dispatch_candidate_users(db, user_ids=user_ids,
        include_leader=payload.include_leader,
        limit=500)
    candidates = [
        {"id": u.id, "name": (u.full_name or u.username or str(u.id))}
        for u in workers
    ]
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="无可用员工用于自动派工，请先在【系统-用户】为员工账号分配「员工」角色，或在【系统-技能标签】维护人员技能")

    default_cap = _get_default_capacity_minutes(db)
    unit = get_capacity_unit(db)
    user_caps = _get_user_capacity_map(db)

    t_rows = db.execute(
        select(Task, Process.workshop, Process.std_minutes)
        .select_from(WorkOrder)
        .join(Task, and_(Task.work_order_id == WorkOrder.id))
        .join(Process, and_(Process.id == Task.process_id))
        .where(WorkOrder.order_id == plan.order_id, Task.status != "done")
        .order_by(Task.id.asc())
    ).all()

    process_ids = list({int(t.process_id) for t, _, _ in t_rows if t.process_id})
    process_skill_map = get_process_skills_map(db, process_ids)
    worker_ids = [int(c["id"]) for c in candidates]
    user_skill_map = build_user_skill_map(db, worker_ids)
    user_dept_map = build_user_department_map(db, worker_ids)
    proficiency_map = user_process_proficiency_map(db, user_ids=worker_ids, process_ids=process_ids
    )

    tasks = []
    for t, workshop, std_minutes in t_rows:
        load = task_load_qty(
            planned_qty=int(t.planned_qty or 0),
            std_minutes=int(std_minutes or 0),
            unit=unit)
        tasks.append({
            "task": t,
            "workshop": (workshop or "未分车间"),
            "minutes": load,
            "process_id": int(t.process_id or 0),
            "required_skills": process_skill_map.get(int(t.process_id or 0), []),
        })

    if not tasks:
        return ok({"assigned_count": 0, "task_count": 0, "span_workdays": span, "users": [], "workshops": [], "overloads": []})

    groups: dict[str, list[dict]] = {}
    for it in tasks:
        if payload.unassigned_only and task_has_assignments(db, it["task"].id):
            continue
        groups.setdefault(it["workshop"], []).append(it)

    assigned = 0
    per_user_total: dict[int, int] = {c["id"]: 0 for c in candidates}
    per_workshop_total: dict[str, int] = {}

    for ws, lst in groups.items():
        lst.sort(key=lambda x: int(x["minutes"]), reverse=True)
        ws_total = 0
        ws_load: dict[int, int] = {c["id"]: 0 for c in candidates}

        for it in lst:
            task_candidates = filter_candidates_for_task(
                candidates,
                required_skill_ids=it.get("required_skills") or [],
                user_skill_map=user_skill_map,
                workshop=it.get("workshop"),
                user_dept_map=user_dept_map)
            if not task_candidates:
                continue
            best_uid = None
            best_score = None
            pid = int(it.get("process_id") or 0)
            for c in task_candidates:
                uid = int(c["id"])
                cap = int(user_caps.get(uid) or default_cap)
                load_score = float(ws_load.get(uid, 0)) / float(cap if cap > 0 else 1)
                prof = proficiency_map.get((uid, pid), 0.5)
                score = load_score - prof * 0.15
                if best_score is None or score < best_score:
                    best_score = score
                    best_uid = uid
            if best_uid is None:
                continue
            try:
                replace_task_assignments(
                    db,
                    task=it["task"],
                    items=[{"user_id": best_uid, "assigned_qty": int(it["task"].planned_qty or 0)}],
                    dispatcher_user_id=user.id)
            except ValueError:
                continue
            ws_load[best_uid] += int(it["minutes"])
            per_user_total[best_uid] = per_user_total.get(best_uid, 0) + int(it["minutes"])
            ws_total += int(it["minutes"])
            assigned += 1
        per_workshop_total[ws] = per_workshop_total.get(ws, 0) + ws_total

    db.commit()

    user_out = []
    overloads = []
    for c in candidates:
        uid = int(c["id"])
        total_m = int(per_user_total.get(uid) or 0)
        daily = round(float(total_m) / float(span), 2)
        cap = int(user_caps.get(uid) or default_cap)
        ol = bool(cap > 0 and float(daily) > float(cap))
        row1 = {
            "user_id": uid,
            "name": c["name"],
            "total_minutes": total_m,
            "daily_minutes": daily,
            "total_load": total_m,
            "daily_load": daily,
            "capacity": cap,
            "overload": ol,
        }
        user_out.append(row1)
        if ol:
            overloads.append({"type": "user", "name": c["name"], "daily_minutes": daily, "daily_load": daily, "capacity": cap})

    ws_caps = _get_workshop_capacity_map(db)
    workshop_out = []
    for ws, total_m in sorted(per_workshop_total.items(), key=lambda x: x[1], reverse=True):
        daily = round(float(total_m) / float(span), 2)
        cap = int(ws_caps.get(ws) or default_cap)
        ol = bool(cap > 0 and float(daily) > float(cap))
        row2 = {
            "workshop": ws,
            "total_minutes": int(total_m),
            "daily_minutes": daily,
            "total_load": int(total_m),
            "daily_load": daily,
            "capacity": cap,
            "overload": ol,
        }
        workshop_out.append(row2)
        if ol:
            overloads.append({"type": "workshop", "name": ws, "daily_minutes": daily, "daily_load": daily, "capacity": cap})

    return ok(
        {
            "assigned_count": assigned,
            "task_count": len(tasks),
            "span_workdays": span,
            "unit": unit,
            "users": user_out,
            "workshops": workshop_out,
            "overloads": overloads,
        }
    )

@router.get("/plans/meta/form-options")
def plan_form_options_api(
    keyword: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """新建生产计划：可选「已审核且未下发投产」的订单。"""
    orders = list_orders(
        db,
        keyword=keyword,
        status="confirmed",
        offset=0,
        limit=200)
    options = []
    for o in orders:
        if order_has_work_orders(db, order_id=o.id):
            continue
        qty = int(
            db.scalar(
                select(func.coalesce(func.sum(OrderItem.qty), 0)).where(OrderItem.order_id == o.id)
            )
            or 0
        )
        options.append(
            {
                "id": o.id,
                "code": o.code,
                "customer_id": o.customer_id,
                "customer_name": o.customer.name if o.customer else None,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "qty": qty,
                "remark": o.remark,
            }
        )
    return ok({"orders": options})

@router.get("/plans")
def list_api(
    status: str | None = Query(default=None),
    order_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    rows = list_plans_with_order_info(
        db,
        status=status,
        order_id=order_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit)
    order_ids = list({int(p.order_id) for p, _, _, _, _ in rows})
    wo_set: set[int] = set()
    progress_map: dict[int, dict] = {}
    if order_ids:
        wo_set = set(
            db.scalars(
                select(WorkOrder.order_id).where(WorkOrder.order_id.in_(order_ids))
            ).all()
        )
        progress_map = get_orders_progress_map(db, order_ids)
    return ok({
        "items": [
            _out(
                plan,
                order_code,
                customer_name,
                qty,
                has_work_orders=int(plan.order_id) in wo_set,
                order_status=order_status,
                done_qty=int((progress_map.get(int(plan.order_id)) or {}).get("done_qty") or 0),
                progress=(progress_map.get(int(plan.order_id)) or {}).get("progress"))
            for plan, order_code, order_status, customer_name, qty in rows
        ]
    })

@router.post("/plans")
def create_api(
    payload: ProductionPlanCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    order = get_order_by_id(db, order_id=payload.order_id, with_items=False)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    if order.status != "confirmed":
        raise HTTPException(status_code=400, detail="仅已审核订单可创建生产计划")
    if order_has_work_orders(db, order_id=order.id):
        raise HTTPException(status_code=400, detail="该订单已下发投产，无需重复建计划")
    from app.services.code_generator import BizType, resolve_code

    plan_code = resolve_code(
        db,
        biz_type=BizType.PRODUCTION_PLAN,
        code=payload.code,
        exists=lambda c: get_plan_by_code(db, c) is not None,
        duplicate_msg="计划编号已存在")
    status = "planned"
    plan = create_plan(
        db,
        order_id=payload.order_id,
        code=plan_code,
        status=status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        work_days=payload.work_days,
        remark=payload.remark,
        created_by=user.id)
    db.commit()
    from app.services.production_automation import maybe_trigger_plan_automation

    pipeline_queued = maybe_trigger_plan_automation(db, plan.id, user.id, "plan_created")
    if pipeline_queued:
        db.commit()
    row = get_plan_with_order_info(db, plan_id=plan.id)
    if not row:
        raise HTTPException(status_code=500, detail="创建失败")
    plan2, order_code, order_status, customer_name, qty = row
    wo_flag = order_has_work_orders(db, order_id=plan2.order_id)
    out = _out(plan2, order_code, customer_name, qty, has_work_orders=wo_flag, order_status=order_status)
    out["pipeline_queued"] = pipeline_queued
    return ok(out)

@router.post("/plans/{plan_id}/release")
def release_plan_api(
    plan_id: int,
    payload: ProductionPlanReleaseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    plan = get_plan_by_id(db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    try:
        result = release_plan(
            db,
            plan=plan,
            releaser_user_id=user.id,
            allow_shortage=payload.allow_shortage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(result)

@router.get("/plans/{plan_id}")
def get_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    plan, order_code, order_status, customer_name, qty = row
    wo_flag = order_has_work_orders(db, order_id=plan.order_id)
    return ok(_out(plan, order_code, customer_name, qty, has_work_orders=wo_flag, order_status=order_status))

@router.put("/plans/{plan_id}")
def update_api(
    plan_id: int,
    payload: ProductionPlanUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=400, detail="生产计划不存在")
    plan, _, _, _, _ = row
    if payload.order_id is not None and payload.order_id != plan.order_id:
        order = get_order_by_id(db, order_id=payload.order_id, with_items=False)
        if not order:
            raise HTTPException(status_code=400, detail="订单不存在")
    if payload.code is not None and payload.code != plan.code:
        exists = get_plan_by_code(db, code=payload.code)
        if exists:
            raise HTTPException(status_code=400, detail="计划编号已存在")
    if payload.status == "in_progress" and plan.status == "planned" and not plan_is_released(plan):
        raise HTTPException(status_code=400, detail="请使用「确认下发」生成工单，不可手动改为进行中")
    update_plan(
        db,
        plan=plan,
        order_id=payload.order_id,
        code=payload.code,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        work_days=payload.work_days,
        remark=payload.remark)
    db.commit()
    from app.services.production_automation import maybe_trigger_plan_automation

    pipeline_queued = maybe_trigger_plan_automation(db, plan_id, user.id, "plan_updated")
    if pipeline_queued:
        db.commit()
    row2 = get_plan_with_order_info(db, plan_id=plan_id)
    if not row2:
        raise HTTPException(status_code=500, detail="更新失败")
    plan2, order_code, order_status, customer_name, qty = row2
    wo_flag = order_has_work_orders(db, order_id=plan2.order_id)
    out = _out(plan2, order_code, customer_name, qty, has_work_orders=wo_flag, order_status=order_status)
    out["pipeline_queued"] = pipeline_queued
    return ok(out)

@router.get("/plans/readiness/preview")
def plan_readiness_preview_api(
    order_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    from app.services.plan_readiness import build_plan_readiness

    try:
        data = build_plan_readiness(db, order_id=order_id, plan_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ok(data)

@router.get("/plans/{plan_id}/readiness")
def plan_readiness_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    from app.services.plan_readiness import build_plan_readiness

    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="生产计划不存在")
    plan, _, _, _, _ = row
    try:
        data = build_plan_readiness(
            db, order_id=plan.order_id, plan_id=plan.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ok(data)

@router.get("/plans/{plan_id}/kitting")
def kitting_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="生产计划不存在")
    plan, order_code, _, customer_name, _ = row
    order = get_order_by_id(db, order_id=plan.order_id, with_items=True)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")

    sku_qty: dict[int, int] = {}
    for it in order.items:
        sku_qty[it.sku_id] = sku_qty.get(it.sku_id, 0) + it.qty
    sku_ids = list(sku_qty.keys())

    bom_by_sku = get_effective_bom_map_by_sku_ids(db, sku_ids=sku_ids)
    missing_boms = []
    for it in order.items:
        if it.sku and it.sku_id not in bom_by_sku:
            missing_boms.append(missing_bom_dict(it.sku, getattr(it.sku, "product", None)))

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

    stock_map = sum_stock_qty_by_sku_ids(db, sku_ids=[v["sku_id"] for v in material_meta.values()])
    items = []
    for mid, demand_qty in demand_by_material.items():
        meta = material_meta[mid]
        stock_qty = stock_map.get(meta["sku_id"], 0)
        shortage_qty = demand_qty - stock_qty
        if shortage_qty < 0:
            shortage_qty = 0
        items.append({**meta, "demand_qty": demand_qty, "stock_qty": stock_qty, "shortage_qty": shortage_qty})
    items.sort(key=lambda x: (x["shortage_qty"] == 0, x["material_id"]))

    return ok(
        {
            "plan_id": plan.id,
            "plan_code": plan.code,
            "order_id": plan.order_id,
            "order_code": order_code,
            "customer_name": customer_name,
            "items": items,
            "missing_boms": missing_boms,
        }
    )

@router.post("/plans/{plan_id}/kitting/create-purchase", dependencies=[Depends(require_permissions(["purchase.manage"]))])
def kitting_create_purchase_api(
    plan_id: int,
    supplier_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="生产计划不存在")
    plan, _, _, _, _ = row
    order = get_order_by_id(db, order_id=plan.order_id, with_items=True)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")

    sku_qty: dict[int, int] = {}
    for it in order.items:
        sku_qty[it.sku_id] = sku_qty.get(it.sku_id, 0) + it.qty
    sku_ids = list(sku_qty.keys())

    bom_by_sku = get_effective_bom_map_by_sku_ids(db, sku_ids=sku_ids)
    missing_sku_ids = [sid for sid in sku_ids if sid not in bom_by_sku]
    if missing_sku_ids:
        raise HTTPException(status_code=400, detail="存在未配置 BOM 的产品型号")

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
            material_meta[m.id] = {"material_id": m.id, "supplier_id": m.supplier_id, "sku_id": m.sku_id}

    stock_map = sum_stock_qty_by_sku_ids(db, sku_ids=[v["sku_id"] for v in material_meta.values()])

    group: dict[int, list[tuple[int, int, float | None, str | None]]] = {}
    missing_supplier_materials = []
    for mid, demand_qty in demand_by_material.items():
        meta = material_meta[mid]
        stock_qty = stock_map.get(meta["sku_id"], 0)
        shortage_qty = demand_qty - stock_qty
        if shortage_qty <= 0:
            continue
        supplier_id = meta["supplier_id"]
        if not supplier_id:
            missing_supplier_materials.append(mid)
            continue
        group.setdefault(int(supplier_id), []).append((mid, int(shortage_qty), None, None))
    if missing_supplier_materials:
        raise HTTPException(status_code=400, detail="存在缺料但未绑定供应商的物料")
    if not group:
        return ok({"items": []})

    created = []
    for sid, items in group.items():
        if supplier_id and sid != int(supplier_id):
            continue
        po = create_purchase_order(
            db,
            supplier_id=sid,
            code=None,
            remark=f"plan:{plan.code}",
            created_by=user.id,
            items=items)
        db.add(PlanPurchaseLink(plan_id=plan.id, purchase_order_id=po.id))
        created.append({"id": po.id, "code": po.code, "supplier_id": sid})
    db.commit()
    return ok({"items": created})

@router.get("/plans/{plan_id}/kitting/purchase-orders")
def kitting_purchase_orders_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="生产计划不存在")

    rows = db.execute(
        select(
            PurchaseOrder.id,
            PurchaseOrder.code,
            PurchaseOrder.status,
            PurchaseOrder.remark,
            PurchaseOrder.created_at,
            Supplier.id.label("supplier_id"),
            Supplier.code.label("supplier_code"),
            Supplier.name.label("supplier_name"),
            func.coalesce(func.sum(PurchaseOrderItem.qty), 0).label("total_qty"),
            func.coalesce(func.sum(PurchaseOrderItem.received_qty), 0).label("received_qty"))
        .join(PlanPurchaseLink, PlanPurchaseLink.purchase_order_id == PurchaseOrder.id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(PurchaseOrderItem, PurchaseOrderItem.order_id == PurchaseOrder.id)
        .where(PlanPurchaseLink.plan_id == plan_id)
        .group_by(PurchaseOrder.id, Supplier.id)
        .order_by(PurchaseOrder.id.desc())
    ).all()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "code": r.code,
                "status": r.status,
                "remark": r.remark,
                "created_at": r.created_at,
                "supplier_id": r.supplier_id,
                "supplier_code": r.supplier_code,
                "supplier_name": r.supplier_name,
                "total_qty": int(r.total_qty or 0),
                "received_qty": int(r.received_qty or 0),
            }
        )
    return ok({"items": items})

@router.get("/plans/{plan_id}/forecast")
def plan_forecast_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.production_forecast import build_plan_forecast

    try:
        return ok(build_plan_forecast(db, plan_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/plans/{plan_id}/aps-strategy", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_aps_strategy_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.aps_strategy_analysis import analyze_aps_strategies

    try:
        return ok(analyze_aps_strategies(db, plan_id, user.id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/plans/{plan_id}/forecast")
def plan_forecast_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.production_forecast import build_plan_forecast

    try:
        return ok(build_plan_forecast(db, plan_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/plans/{plan_id}/aps-strategy", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_aps_strategy_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.aps_strategy_analysis import analyze_aps_strategies

    try:
        return ok(analyze_aps_strategies(db, plan_id, user.id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
