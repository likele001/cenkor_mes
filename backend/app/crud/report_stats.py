from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.process import Process
from app.models.report import Report
from app.models.task import Task


def _datetime_range(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    start_dt = datetime.combine(date_from, time.min) if date_from else None
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None
    return start_dt, end_dt


def get_production_summary(db: Session, date_from: date | None, date_to: date | None) -> dict:
    start_dt, end_dt = _datetime_range(date_from, date_to)
    stmt = select(
        func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
        func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
        func.count(Report.id).label("report_count"),
    ).where(Report.status == "qc_approved")
    if start_dt:
        stmt = stmt.where(Report.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(Report.created_at < end_dt)
    row = db.execute(stmt).one()
    good_qty = int(row.good_qty or 0)
    bad_qty = int(row.bad_qty or 0)
    total_qty = good_qty + bad_qty
    return {
        "good_qty": good_qty,
        "bad_qty": bad_qty,
        "total_qty": total_qty,
        "yield_rate": round(good_qty / total_qty, 6) if total_qty > 0 else None,
        "report_count": int(row.report_count or 0),
    }


def get_yield_summary(db: Session, date_from: date | None, date_to: date | None) -> dict:
    data = get_production_summary(db, date_from=date_from, date_to=date_to)
    return {"yield_rate": data["yield_rate"], "good_qty": data["good_qty"], "bad_qty": data["bad_qty"], "total_qty": data["total_qty"]}


def get_process_rank(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    limit: int = 20,
) -> list[dict]:
    start_dt, end_dt = _datetime_range(date_from, date_to)
    stmt = (
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
        .order_by(func.sum(Report.good_qty).desc(), func.sum(Report.bad_qty).asc())
        .limit(limit)
    )
    if start_dt:
        stmt = stmt.where(Report.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(Report.created_at < end_dt)
    rows = db.execute(stmt).all()
    items: list[dict] = []
    for r in rows:
        good_qty = int(r.good_qty or 0)
        bad_qty = int(r.bad_qty or 0)
        total_qty = good_qty + bad_qty
        items.append(
            {
                "process_id": int(r.process_id),
                "process_name": r.process_name,
                "good_qty": good_qty,
                "bad_qty": bad_qty,
                "total_qty": total_qty,
                "yield_rate": round(good_qty / total_qty, 6) if total_qty > 0 else None,
            }
        )
    return items


def get_daily_trend(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    start_dt, end_dt = _datetime_range(date_from, date_to)
    day_col = func.date(Report.created_at).label("day")
    stmt = (
        select(
            day_col,
            func.coalesce(func.sum(Report.good_qty), 0).label("good_qty"),
            func.coalesce(func.sum(Report.bad_qty), 0).label("bad_qty"),
        )
        .where(Report.status == "qc_approved")
        .group_by(day_col)
        .order_by(day_col.asc())
    )
    if start_dt:
        stmt = stmt.where(Report.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(Report.created_at < end_dt)
    rows = db.execute(stmt).all()
    by_day: dict[date, dict] = {}
    for r in rows:
        d: date = r.day if isinstance(r.day, date) else date.fromisoformat(str(r.day))
        good_qty = int(r.good_qty or 0)
        bad_qty = int(r.bad_qty or 0)
        total_qty = good_qty + bad_qty
        by_day[d] = {
            "date": d.isoformat(),
            "good_qty": good_qty,
            "bad_qty": bad_qty,
            "total_qty": total_qty,
            "yield_rate": round(good_qty / total_qty, 6) if total_qty > 0 else None,
        }

    if date_from and date_to and date_to >= date_from and (date_to - date_from).days <= 366:
        out: list[dict] = []
        cur = date_from
        while cur <= date_to:
            out.append(by_day.get(cur) or {"date": cur.isoformat(), "good_qty": 0, "bad_qty": 0, "total_qty": 0, "yield_rate": None})
            cur += timedelta(days=1)
        return out

    return [by_day[d] for d in sorted(by_day.keys())]
