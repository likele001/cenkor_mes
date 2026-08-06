"""Causal inference engine - basic statistical association + enhanced redirect."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.task import Task
from app.models.work_order import WorkOrder


def analyze_yield_causes(db: Session, *, days: int = 30) -> dict:
    """Basic yield analysis (kept for backward compatibility)."""
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(Task.process_id, func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .join(Report, Report.task_id == Task.id)
        .where(
            Report.status == "qc_approved",
            func.date(Report.created_at) >= since,
        )
        .group_by(Task.process_id)
    ).all()
    causes = []
    total_good = sum(int(r[1] or 0) for r in rows)
    total_bad = sum(int(r[2] or 0) for r in rows)
    for pid, g, b in rows:
        good = int(g or 0)
        bad = int(b or 0)
        total = good + bad
        if total > 0 and bad > 0:
            causes.append({
                "process_id": pid,
                "good": good,
                "bad": bad,
                "yield_rate": round(good / total * 100, 1),
                "bad_share_pct": round(bad / max(total_bad, 1) * 100, 1),
            })
    causes.sort(key=lambda x: x["bad_share_pct"], reverse=True)
    return {
        "ok": True,
        "days": days,
        "total_good": total_good,
        "total_bad": total_bad,
        "causes": causes[:10],
    }


def analyze_yield_causes_enhanced(db: Session, *, days: int = 30) -> dict:
    """Enhanced causal analysis (L3+) with trend analysis and hypothesis generation."""
    try:
        from app.services.ai.causal.enhanced_causal import analyze_yield_causes_enhanced as _enhanced
        return _enhanced(db, days=days)
    except Exception as e:
        return analyze_yield_causes(db, days=days)