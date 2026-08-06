"""Digital twin - rule-based basic + enhanced redirect."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.process import Process
from app.models.task import Task
from app.models.work_order import WorkOrder


def workshop_twin_snapshot(db: Session) -> dict:
    """Basic workshop load snapshot (kept for backward compatibility)."""
    rows = db.execute(
        select(Process.workshop, Task.status, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(Task.status.in_(("pending", "working")))
        .group_by(Process.workshop, Task.status)
    ).all()
    workshops: dict = {}
    for ws, status, cnt in rows:
        if ws not in workshops:
            workshops[ws] = {"pending": 0, "working": 0, "total": 0}
        workshops[ws][status] = int(cnt or 0)
        workshops[ws]["total"] += int(cnt or 0)
    return {"ok": True, "workshops": workshops}


def workshop_twin_enhanced(db: Session, *, days: int = 7) -> dict:
    """Enhanced digital twin (L3+) - loads the enhanced_twin module."""
    try:
        from app.services.ai.twin.enhanced_twin import workshop_twin_enhanced as _enhanced
        return _enhanced(db, days=days)
    except Exception as e:
        # Graceful fallback to basic snapshot
        return workshop_twin_snapshot(db)