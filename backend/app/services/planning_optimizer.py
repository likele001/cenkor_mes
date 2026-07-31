"""OR-Tools 约束排产（与 LLM 建议对比，人工选用）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.crud.order import get_order_by_id
from app.crud.production_calendar import get_calendar_day
from app.crud.production_plan import get_plan_by_id
from app.models.process import Process
from app.models.task import Task
from app.models.work_order import WorkOrder


def _get_workdays_setting(db: Session, tenant_id: int) -> list[int]:
    from app.crud.tenant_setting import get_setting
    import json

    row = get_setting(db, tenant_id, "plan.workdays")
    if row and row.value:
        try:
            data = json.loads(row.value)
            if isinstance(data, list):
                return [int(x) for x in data if 1 <= int(x) <= 7]
        except Exception:
            pass
    return [1, 2, 3, 4, 5]


def _is_workday(db: Session, tenant_id: int, d: date, workdays: list[int]) -> bool:
    it = get_calendar_day(db, tenant_id=tenant_id, day=d)
    if it is not None:
        return bool(it.is_workday)
    return int(d.isoweekday()) in workdays


def _shift_workdays(db: Session, tenant_id: int, d: date, delta: int, workdays: list[int]) -> date:
    if delta == 0:
        return d
    step = 1 if delta > 0 else -1
    remain = abs(delta)
    cur = d
    while remain > 0:
        cur = cur + timedelta(days=step)
        for _ in range(400):
            if _is_workday(db, tenant_id, cur, workdays):
                break
            cur = cur + timedelta(days=step)
        remain -= 1
    return cur


def _total_minutes(db: Session, tenant_id: int, order_id: int) -> int:
    row = db.execute(
        select(func.coalesce(func.sum(Task.planned_qty * func.coalesce(Process.std_minutes, 1)), 0))
        .select_from(WorkOrder)
        .join(Task, and_(Task.tenant_id == WorkOrder.tenant_id, Task.work_order_id == WorkOrder.id))
        .join(Process, and_(Process.tenant_id == Task.tenant_id, Process.id == Task.process_id))
        .where(WorkOrder.tenant_id == tenant_id, WorkOrder.order_id == order_id, Task.status != "done")
    ).scalar()
    return int(row or 0)


def _daily_capacity(db: Session, tenant_id: int, d: date, default_cap: int = 480) -> int:
    it = get_calendar_day(db, tenant_id=tenant_id, day=d)
    if it is not None and it.capacity_minutes:
        return int(it.capacity_minutes)
    return default_cap


def _forward_schedule_fallback(
    db: Session,
    tenant_id: int,
    *,
    workdays: list[int],
    work_day_count: int,
    total_mins: int,
    note: str,
) -> dict:
    """无订单交期/计划结束日时，从今日起按默认工期正排。"""
    wdc = max(1, int(work_day_count))
    start = date.today()
    for _ in range(400):
        if _is_workday(db, tenant_id, start, workdays):
            break
        start += timedelta(days=1)
    end = _shift_workdays(db, tenant_id, start, wdc - 1, workdays)
    return {
        "ok": True,
        "solver": "fallback_forward",
        "suggest_mode": "forward",
        "suggest_start_date": start.isoformat(),
        "suggest_end_date": end.isoformat(),
        "suggest_work_days": wdc,
        "total_minutes": total_mins,
        "notes": [note],
    }


def optimize_plan_schedule(db: Session, tenant_id: int, plan_id: int) -> dict:
    """
    基于总工时与日历产能，倒排求可行 start/end。
    优先 OR-Tools CP-SAT；未安装时规则倒排。
    """
    plan = get_plan_by_id(db, tenant_id=tenant_id, plan_id=plan_id)
    if not plan:
        return {"ok": False, "error": "计划不存在"}
    order = get_order_by_id(db, tenant_id=tenant_id, order_id=plan.order_id, with_items=False)
    if not order:
        return {"ok": False, "error": "订单不存在"}

    due = order.due_date or plan.end_date

    workdays = _get_workdays_setting(db, tenant_id)
    total_mins = _total_minutes(db, tenant_id, plan.order_id)
    if total_mins <= 0:
        total_mins = int(plan.work_days or 1) * 480

    work_day_count = max(1, (total_mins + 480 - 1) // 480)
    if plan.work_days and int(plan.work_days) > 0:
        work_day_count = max(work_day_count, int(plan.work_days))

    if not due:
        return _forward_schedule_fallback(
            db,
            tenant_id,
            workdays=workdays,
            work_day_count=work_day_count,
            total_mins=total_mins,
            note="订单未设置交期，已从今日正排默认工期（可在计划中调整起止日）",
        )

    default_cap = 480
    from app.crud.tenant_setting import get_setting
    import json

    cap_row = get_setting(db, tenant_id, "plan.default_capacity_minutes")
    if cap_row and cap_row.value:
        try:
            default_cap = int(json.loads(cap_row.value) if cap_row.value.startswith("[") else cap_row.value)
        except Exception:
            try:
                default_cap = int(cap_row.value)
            except Exception:
                pass

    # 收集工作日窗口（交期前最多 120 自然日）
    days: list[date] = []
    cur = due
    for _ in range(120):
        if _is_workday(db, tenant_id, cur, workdays):
            days.append(cur)
        cur -= timedelta(days=1)
        if len(days) >= 60:
            break
    days.reverse()
    if not days:
        days = [due]

    caps = [_daily_capacity(db, tenant_id, d, default_cap) for d in days]
    n = len(days)

    solver_used = "rule"
    work_day_count = max(1, (total_mins + default_cap - 1) // default_cap)

    try:
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        x = [model.new_bool_var(f"d{i}") for i in range(n)]
        model.add(sum(x[i] * caps[i] for i in range(n)) >= total_mins)
        # 尽量靠后（接近交期）
        model.maximize(sum(x[i] * (i + 1) for i in range(n)))
        # 限制连续工作日数量
        model.add(sum(x) <= max(work_day_count + 5, 30))
        model.add(sum(x) >= min(work_day_count, n))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            picked = [days[i] for i in range(n) if solver.value(x[i])]
            if picked:
                start, end = picked[0], picked[-1]
                solver_used = "ortools"
                return {
                    "ok": True,
                    "solver": solver_used,
                    "suggest_mode": "backward",
                    "suggest_start_date": start.isoformat(),
                    "suggest_end_date": end.isoformat(),
                    "suggest_work_days": len(picked),
                    "total_minutes": total_mins,
                    "notes": [f"OR-Tools 在 {len(picked)} 个工作日内分配 {total_mins} 分钟产能"],
                }
    except ImportError:
        pass
    except Exception as e:
        return {
            "ok": True,
            "solver": "rule",
            "suggest_mode": "backward",
            "suggest_start_date": _shift_workdays(db, tenant_id, due, -(work_day_count - 1), workdays).isoformat(),
            "suggest_end_date": due.isoformat(),
            "suggest_work_days": work_day_count,
            "total_minutes": total_mins,
            "notes": [f"OR-Tools 不可用({str(e)[:80]})，已用规则倒排"],
        }

    end = due
    for _ in range(400):
        if _is_workday(db, tenant_id, end, workdays):
            break
        end -= timedelta(days=1)
    start = _shift_workdays(db, tenant_id, end, -(work_day_count - 1), workdays)
    return {
        "ok": True,
        "solver": solver_used,
        "suggest_mode": "backward",
        "suggest_start_date": start.isoformat(),
        "suggest_end_date": end.isoformat(),
        "suggest_work_days": work_day_count,
        "total_minutes": total_mins,
        "notes": ["规则倒排：按默认日产能估算工期"],
    }
