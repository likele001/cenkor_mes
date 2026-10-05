# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""计划自动派工 — 手动派工接口与自动化编排共用的唯一实现

这里曾是旧的 tenant_id 签名版本，与 crud 的真实签名长期脱节（只在自动化链路
被调用，所以一直没炸）。现在 plans API 的手动派工也委托过来，避免两份逻辑再次漂移。
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.production_calendar import list_calendar_days
from app.crud.production_plan import (
    ensure_plan_released_for_dispatch,
    get_plan_by_id,
    get_plan_with_order_info,
)
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
        out = [int(x) for x in v if 1 <= int(x) <= 7]
        return out or list(_CAL_DEFAULT_WORKDAYS)
    except (ValueError, TypeError):
        return list(_CAL_DEFAULT_WORKDAYS)


def _calendar_map(db: Session, date_from: date, date_to: date):
    return {it.day: it for it in list_calendar_days(db, date_from=date_from, date_to=date_to)}


def _is_workday(day0: date, *, workdays: list[int], cal_map) -> bool:
    it = cal_map.get(day0)
    if it is not None:
        return bool(it.is_workday)
    return int(day0.isoweekday()) in workdays


def execute_auto_dispatch(
    db: Session,
    *,
    plan_id: int,
    user_id: int,
    payload: AutoDispatchIn,
) -> dict:
    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise ValueError("生产计划不存在")
    plan, _, _, _, _ = row

    release_info = ensure_plan_released_for_dispatch(
        db,
        plan=plan,
        releaser_user_id=user_id,
        auto_release=payload.auto_release,
        allow_shortage=payload.allow_shortage,
    )
    if release_info is not None:
        db.commit()

    row = get_plan_with_order_info(db, plan_id=plan_id)
    if not row:
        raise ValueError("生产计划不存在")
    plan, _, _, _, _ = row
    if plan.status == "planned":
        raise ValueError(
            "生产计划尚未「确认下发」。订单「审核通过」不等于计划已下发，"
            "请在【生产计划】列表点击「确认下发」后再派工。")
    if not plan.start_date or not plan.end_date:
        raise ValueError("请先设置计划开始/结束日期")

    workdays = _get_workdays_setting(db)
    cal_map = _calendar_map(db, date_from=plan.start_date, date_to=plan.end_date)
    span = 0
    cur = plan.start_date
    while cur <= plan.end_date:
        if _is_workday(cur, workdays=workdays, cal_map=cal_map):
            span += 1
        cur += timedelta(days=1)
    span = max(1, span)

    workers = list_dispatch_candidate_users(
        db,
        user_ids=payload.user_ids,
        include_leader=payload.include_leader,
        limit=500,
    )
    candidates = [{"id": u.id, "name": (u.full_name or u.username or str(u.id))} for u in workers]
    if not candidates:
        raise ValueError(
            "无可用员工用于自动派工，请先在【系统-用户】为员工账号分配「员工」角色，"
            "或在【系统-技能标签】维护人员技能")

    default_cap = get_default_capacity(db)
    unit = get_capacity_unit(db)
    user_caps = get_user_capacity_map(db)

    t_rows = db.execute(
        select(Task, Process.workshop, Process.std_minutes)
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(WorkOrder.order_id == plan.order_id, Task.status != "done")
        .order_by(Task.id.asc())
    ).all()

    process_ids = list({int(t.process_id) for t, _, _ in t_rows if t.process_id})
    process_skill_map = get_process_skills_map(db, process_ids)
    worker_ids = [int(c["id"]) for c in candidates]
    user_skill_map = build_user_skill_map(db, worker_ids)
    user_dept_map = build_user_department_map(db, worker_ids)
    proficiency_map = user_process_proficiency_map(db, user_ids=worker_ids, process_ids=process_ids)

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
        return {
            "assigned_count": 0, "task_count": 0, "span_workdays": span, "unit": unit,
            "users": [], "workshops": [], "overloads": [], "release": release_info,
        }

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
                    dispatcher_user_id=user_id)
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
        user_out.append({
            "user_id": uid,
            "name": c["name"],
            "total_minutes": total_m,
            "daily_minutes": daily,
            "total_load": total_m,
            "daily_load": daily,
            "capacity": cap,
            "overload": ol,
        })
        if ol:
            overloads.append({"type": "user", "name": c["name"], "daily_minutes": daily, "daily_load": daily, "capacity": cap})

    ws_caps = get_workshop_capacity_map(db)
    workshop_out = []
    for ws, total_m in sorted(per_workshop_total.items(), key=lambda x: x[1], reverse=True):
        daily = round(float(total_m) / float(span), 2)
        cap = int(ws_caps.get(ws) or default_cap)
        ol = bool(cap > 0 and float(daily) > float(cap))
        workshop_out.append({
            "workshop": ws,
            "total_minutes": int(total_m),
            "daily_minutes": daily,
            "total_load": int(total_m),
            "daily_load": daily,
            "capacity": cap,
            "overload": ol,
        })
        if ol:
            overloads.append({"type": "workshop", "name": ws, "daily_minutes": daily, "daily_load": daily, "capacity": cap})

    return {
        "assigned_count": assigned,
        "task_count": len(tasks),
        "span_workdays": span,
        "unit": unit,
        "users": user_out,
        "workshops": workshop_out,
        "overloads": overloads,
        "release": release_info,
    }
