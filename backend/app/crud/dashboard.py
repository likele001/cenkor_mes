from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.salary import SalaryItem
from app.models.task import Task


def get_dashboard_summary(db: Session, today: date | None = None) -> dict:
    if today is None:
        today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = start_dt + timedelta(days=1)

    row = db.execute(
        select(
            func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
            func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
            func.count(Report.id).label("report_count"),
        ).where(
            Report.status == "qc_approved",
            Report.created_at >= start_dt,
            Report.created_at < end_dt,
        )
    ).one()
    today_good_qty = int(row.good_qty or 0)
    today_bad_qty = int(row.bad_qty or 0)
    today_total_qty = today_good_qty + today_bad_qty
    today_yield_rate = round(today_good_qty / today_total_qty, 6) if today_total_qty > 0 else None

    pending_legacy = int(
        db.scalar(
            select(func.count(Report.id)).where(
                Report.status.in_(("submitted", "leader_approved")),
            )
        )
        or 0
    )
    pending_units = int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.status.in_(("submitted", "leader_approved")),
            )
        )
        or 0
    )
    pending_report_count = pending_legacy + pending_units

    orders_total = int(db.scalar(select(func.count(Order.id))) or 0)
    orders_confirmed = int(
        db.scalar(select(func.count(Order.id)).where(Order.status == "confirmed")) or 0
    )

    tasks_total = int(db.scalar(select(func.count(Task.id))) or 0)
    tasks_pending = int(
        db.scalar(select(func.count(Task.id)).where(Task.status == "pending")) or 0
    )
    tasks_done = int(db.scalar(select(func.count(Task.id)).where(Task.status == "done")) or 0)

    today_salary_amount = db.scalar(
        select(func.coalesce(func.sum(SalaryItem.amount), 0)).where(
            SalaryItem.created_at >= start_dt,
            SalaryItem.created_at < end_dt,
        )
    )

    return {
        "today": {
            "date": today.isoformat(),
            "good_qty": today_good_qty,
            "bad_qty": today_bad_qty,
            "total_qty": today_total_qty,
            "yield_rate": today_yield_rate,
            "report_count": int(row.report_count or 0),
            "salary_amount": float(today_salary_amount or 0),
        },
        "orders": {"total": orders_total, "confirmed": orders_confirmed},
        "tasks": {"total": tasks_total, "pending": tasks_pending, "done": tasks_done},
        "reports": {"pending_audit": pending_report_count},
    }


def get_dashboard_charts(db: Session, days: int = 14) -> dict:
    """首页趋势图数据：日报工趋势 + 工序排名"""
    today = date.today()
    date_from = today - timedelta(days=days - 1)

    # ── 日趋势 ──
    day_col = func.date(Report.created_at).label("day")
    trend_rows = db.execute(
        select(
            day_col,
            func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
            func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
        )
        .where(
            Report.status == "qc_approved",
            Report.created_at >= datetime.combine(date_from, time.min),
            Report.created_at < datetime.combine(today + timedelta(days=1), time.min),
        )
        .group_by(day_col)
        .order_by(day_col.asc())
    ).all()

    by_day: dict[str, dict] = {}
    for r in trend_rows:
        d = r.day.isoformat() if isinstance(r.day, date) else str(r.day)[:10]
        g = int(r.good_qty or 0)
        b = int(r.bad_qty or 0)
        by_day[d] = {"date": d, "good_qty": g, "bad_qty": b, "total_qty": g + b}

    daily_trend: list[dict] = []
    cur = date_from
    while cur <= today:
        ds = cur.isoformat()
        daily_trend.append(by_day.get(ds) or {"date": ds, "good_qty": 0, "bad_qty": 0, "total_qty": 0})
        cur += timedelta(days=1)

    # ── 工序排名 ──
    from app.models.process import Process
    from app.models.task import Task

    rank_rows = db.execute(
        select(
            Task.process_id.label("process_id"),
            Process.name.label("process_name"),
            func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
            func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
        )
        .select_from(Report)
        .join(Task, Task.id == Report.task_id)
        .join(Process, Process.id == Task.process_id)
        .where(
            Report.status == "qc_approved",
        )
        .group_by(Task.process_id, Process.name)
        .order_by(func.sum(Report.good_qty).desc())
        .limit(10)
    ).all()

    process_rank = [
        {
            "process_id": int(r.process_id),
            "process_name": r.process_name,
            "good_qty": int(r.good_qty or 0),
            "bad_qty": int(r.bad_qty or 0),
        }
        for r in rank_rows
    ]

    return {"daily_trend": daily_trend, "process_rank": process_rank}


def get_employee_dashboard_summary(db: Session, user_id: int, today: date | None = None) -> dict:
    """H5 员工个人首页仪表盘数据（仅当前用户）"""
    if today is None:
        today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = start_dt + timedelta(days=1)

    today_row = db.execute(
        select(
            func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
            func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
        ).where(
            Report.report_user_id == user_id,
            Report.created_at >= start_dt,
            Report.created_at < end_dt,
        )
    ).one()
    unit_good = int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.user_id == user_id,
                ReportUnit.result_type == "good",
                ReportUnit.submitted_at >= start_dt,
                ReportUnit.submitted_at < end_dt,
            )
        )
        or 0
    )
    unit_bad = int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.user_id == user_id,
                ReportUnit.result_type == "bad",
                ReportUnit.submitted_at >= start_dt,
                ReportUnit.submitted_at < end_dt,
            )
        )
        or 0
    )
    today_good = int(today_row.good_qty or 0) + unit_good
    today_bad = int(today_row.bad_qty or 0) + unit_bad
    today_total = today_good + today_bad
    today_yield = round(today_good / today_total, 6) if today_total > 0 else None

    # 今日工资预估
    today_salary = db.scalar(
        select(func.coalesce(func.sum(SalaryItem.amount), 0)).where(
            SalaryItem.created_at >= start_dt,
            SalaryItem.created_at < end_dt,
            SalaryItem.user_id == user_id,
        )
    ) or 0

    from app.models.task_assignment import TaskAssignment

    def _count_my_tasks(task_status: str) -> int:
        return int(
            db.scalar(
                select(func.count(func.distinct(Task.id)))
                .select_from(Task)
                .join(
                    TaskAssignment,
                    TaskAssignment.task_id == Task.id,
                )
                .where(
                    TaskAssignment.user_id == user_id,
                    Task.status == task_status,
                )
            )
            or 0
        )

    my_pending_tasks = _count_my_tasks("pending")
    my_working_tasks = _count_my_tasks("working")

    # 本月工资汇总
    month_start = date(today.year, today.month, 1)
    month_salary = db.scalar(
        select(func.coalesce(func.sum(SalaryItem.amount), 0)).where(
            SalaryItem.user_id == user_id,
            SalaryItem.created_at >= datetime.combine(month_start, time.min),
            SalaryItem.created_at < end_dt,
        )
    ) or 0

    # 本月报工总数
    month_legacy = int(
        db.scalar(
            select(func.count(Report.id)).where(
                Report.report_user_id == user_id,
                Report.created_at >= datetime.combine(month_start, time.min),
                Report.created_at < end_dt,
            )
        )
        or 0
    )
    month_units = int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.user_id == user_id,
                ReportUnit.status != "draft",
                ReportUnit.submitted_at >= datetime.combine(month_start, time.min),
                ReportUnit.submitted_at < end_dt,
            )
        )
        or 0
    )
    month_report_count = month_legacy + month_units

    return {
        "today": {
            "date": today.isoformat(),
            "good_qty": today_good,
            "bad_qty": today_bad,
            "total_qty": today_total,
            "yield_rate": today_yield,
            "salary_amount": float(today_salary),
        },
        "my_tasks": {
            "pending": my_pending_tasks,
            "working": my_working_tasks,
            "total": my_pending_tasks + my_working_tasks,
        },
        "month": {
            "month": today.strftime("%Y-%m"),
            "report_count": month_report_count,
            "salary_amount": float(month_salary),
        },
    }
