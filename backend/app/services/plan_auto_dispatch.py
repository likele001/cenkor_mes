"""计划自动派工（从 plans API 抽取，供自动化编排复用）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.crud.production_calendar import get_calendar_day, list_calendar_days
from app.crud.production_plan import ensure_plan_released_for_dispatch, get_plan_by_id, get_plan_with_order_info
from app.crud.task_assignment import replace_task_assignments, task_has_assignments
from app.crud.tenant_setting import get_setting
from app.crud.process_skill import get_process_skills_map
from app.models.process import Process
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.schemas.production_plan import AutoDispatchIn
from app.services.dispatch_candidates import (
    build_user_department_map,
    build_user_skill_map,
    filter_candidates_for_task,
    list_dispatch_candidate_users,
)
from app.services.dispatch_proficiency import user_process_proficiency_map
from app.services.plan_capacity_settings import (
    get_capacity_unit,
    get_default_capacity,
    get_user_capacity_map,
    get_workshop_capacity_map,
    task_load_qty,
)
import json


def _get_workdays_setting(db: Session, tenant_id: int) -> list[int]:
    it = get_setting(db, tenant_id=tenant_id, key="plan.calendar.workdays")
    if not it or not it.value:
        return [1, 2, 3, 4, 5, 6]
    try:
        v = json.loads(it.value)
        if not isinstance(v, list):
            return [1, 2, 3, 4, 5, 6]
        out = [int(x) for x in v if 1 <= int(x) <= 7]
        return out or [1, 2, 3, 4, 5, 6]
    except Exception:
        return [1, 2, 3, 4, 5, 6]


def _calendar_map(db: Session, tenant_id: int, date_from: date, date_to: date):
    rows = list_calendar_days(db, tenant_id=tenant_id, date_from=date_from, date_to=date_to)
    return {it.day: it for it in rows}


def _is_workday(day0: date, *, workdays: list[int], cal_map) -> bool:
    it = cal_map.get(day0)
    if it is not None:
        return bool(it.is_workday)
    return int(day0.isoweekday()) in workdays


def execute_auto_dispatch(
    db: Session,
    *,
    tenant_id: int,
    plan_id: int,
    user_id: int,
    payload: AutoDispatchIn,
) -> dict:
    row = get_plan_with_order_info(db, tenant_id=tenant_id, plan_id=plan_id)
    if not row:
        raise ValueError("生产计划不存在")
    plan, _, _, _, _ = row

    release_info = ensure_plan_released_for_dispatch(
        db,
        tenant_id=tenant_id,
        plan=plan,
        releaser_user_id=user_id,
        auto_release=payload.auto_release,
        allow_shortage=payload.allow_shortage,
    )
    if release_info is not None:
        db.flush()

    plan = get_plan_by_id(db, tenant_id=tenant_id, plan_id=plan_id)
    if not plan:
        raise ValueError("生产计划不存在")
    if plan.status == "planned":
        raise ValueError("生产计划尚未确认下发，无法派工")
    if not plan.start_date or not plan.end_date:
        raise ValueError("请先设置计划开始/结束日期")

    workdays = _get_workdays_setting(db, tenant_id)
    cal_map = _calendar_map(db, tenant_id=tenant_id, date_from=plan.start_date, date_to=plan.end_date)
    span = 0
    cur = plan.start_date
    while cur <= plan.end_date:
        if _is_workday(cur, workdays=workdays, cal_map=cal_map):
            span += 1
        cur += timedelta(days=1)
    if span <= 0:
        span = 1

    workers = list_dispatch_candidate_users(
        db,
        tenant_id,
        user_ids=payload.user_ids,
        include_leader=payload.include_leader,
        limit=500,
    )
    candidates = [{"id": u.id, "name": (u.full_name or u.username or str(u.id))} for u in workers]
    if not candidates:
        raise ValueError("无可用员工用于自动派工，请维护员工角色与技能")

    default_cap = get_default_capacity(db, tenant_id=tenant_id)
    unit = get_capacity_unit(db, tenant_id=tenant_id)
    user_caps = get_user_capacity_map(db, tenant_id=tenant_id)

    t_rows = db.execute(
        select(Task, Process.workshop, Process.std_minutes)
        .select_from(WorkOrder)
        .join(Task, and_(Task.tenant_id == WorkOrder.tenant_id, Task.work_order_id == WorkOrder.id))
        .join(Process, and_(Process.tenant_id == Task.tenant_id, Process.id == Task.process_id))
        .where(WorkOrder.tenant_id == tenant_id, WorkOrder.order_id == plan.order_id, Task.status != "done")
        .order_by(Task.id.asc())
    ).all()

    process_ids = list({int(t.process_id) for t, _, _ in t_rows if t.process_id})
    process_skill_map = get_process_skills_map(db, tenant_id, process_ids)
    worker_ids = [int(c["id"]) for c in candidates]
    user_skill_map = build_user_skill_map(db, tenant_id, worker_ids)
    user_dept_map = build_user_department_map(db, tenant_id, worker_ids)
    proficiency_map = user_process_proficiency_map(db, tenant_id, user_ids=worker_ids, process_ids=process_ids)

    tasks = []
    for t, workshop, std_minutes in t_rows:
        load = task_load_qty(planned_qty=int(t.planned_qty or 0), std_minutes=int(std_minutes or 0), unit=unit)
        tasks.append({
            "task": t,
            "workshop": (workshop or "未分车间"),
            "minutes": load,
            "process_id": int(t.process_id or 0),
            "required_skills": process_skill_map.get(int(t.process_id or 0), []),
        })

    if not tasks:
        return {"assigned_count": 0, "task_count": 0, "span_workdays": span, "release": release_info}

    groups: dict[str, list[dict]] = {}
    for it in tasks:
        if payload.unassigned_only and task_has_assignments(db, tenant_id, it["task"].id):
            continue
        groups.setdefault(it["workshop"], []).append(it)

    assigned = 0
    per_user_total: dict[int, int] = {c["id"]: 0 for c in candidates}

    for _ws, lst in groups.items():
        lst.sort(key=lambda x: int(x["minutes"]), reverse=True)
        ws_load: dict[int, int] = {c["id"]: 0 for c in candidates}
        for it in lst:
            task_candidates = filter_candidates_for_task(
                candidates,
                required_skill_ids=it.get("required_skills") or [],
                user_skill_map=user_skill_map,
                workshop=it.get("workshop"),
                user_dept_map=user_dept_map,
            )
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
                    tenant_id=tenant_id,
                    task=it["task"],
                    items=[{"user_id": best_uid, "assigned_qty": int(it["task"].planned_qty or 0)}],
                    dispatcher_user_id=user_id,
                )
            except ValueError:
                continue
            ws_load[best_uid] += int(it["minutes"])
            per_user_total[best_uid] = per_user_total.get(best_uid, 0) + int(it["minutes"])
            assigned += 1

    return {
        "assigned_count": assigned,
        "task_count": len(tasks),
        "span_workdays": span,
        "release": release_info,
    }
