# -*- coding: utf-8 -*-
"""Enhanced digital twin - workshop snapshot + predicted load + bottleneck analysis."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def workshop_twin_enhanced(db: Session, *, days: int = 7) -> dict:
    """Enhanced workshop snapshot with trend data and bottleneck identification."""
    from app.models.process import Process
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    # Current snapshot (load by workshop/status)
    rows = db.execute(
        select(Process.workshop, Task.status, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(
            Task.status.in_(("pending", "working")),
        )
        .group_by(Process.workshop, Task.status)
    ).all()

    workshops: dict = {}
    for ws, status, cnt in rows:
        if ws not in workshops:
            workshops[ws] = {"pending": 0, "working": 0, "total": 0}
        workshops[ws][status] = int(cnt or 0)
        workshops[ws]["total"] += int(cnt or 0)

    # Per-process load and bottleneck detection
    process_rows = db.execute(
        select(Process.id, Process.workshop, Task.status, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(
            Task.status.in_(("pending", "working")),
        )
        .group_by(Process.id, Process.workshop, Task.status)
    ).all()

    processes: dict = {}
    for pid, ws, status, cnt in process_rows:
        if pid not in processes:
            processes[pid] = {"workshop": ws, "pending": 0, "working": 0, "total": 0}
        processes[pid][status] = int(cnt or 0)
        processes[pid]["total"] += int(cnt or 0)

    # Identify bottleneck (highest pending tasks)
    bottleneck = None
    if processes:
        max_pending_proc = max(processes.items(), key=lambda x: x[1].get("pending", 0))
        if max_pending_proc[1].get("pending", 0) >= 5:
            bottleneck = {
                "process_id": max_pending_proc[0],
                "workshop": max_pending_proc[1].get("workshop"),
                "pending_count": max_pending_proc[1].get("pending", 0),
                "total": max_pending_proc[1].get("total", 0),
                "reason": "pending queue is long",
            }

    # Historical trend (last N days)
    since = date.today() - timedelta(days=days)
    trend_rows = db.execute(
        select(Process.workshop, func.date(Task.created_at), func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(func.date(Task.created_at) >= since)
        .group_by(Process.workshop, func.date(Task.created_at))
    ).all()

    trend_data: dict = {}
    for ws, d, cnt in trend_rows:
        if ws not in trend_data:
            trend_data[ws] = []
        trend_data[ws].append({"date": str(d), "count": int(cnt or 0)})

    return {
        "ok": True,
        "workshops": workshops,
        "processes": processes,
        "bottleneck": bottleneck,
        "trend": trend_data,
    }


def identify_bottleneck(db: Session, *, threshold: int = 5) -> dict:
    """Identify workshop bottlenecks by pending task volume."""
    from app.models.process import Process
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    rows = db.execute(
        select(Process.id, Process.workshop, Process.name, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(Task.status == "pending")
        .group_by(Process.id, Process.workshop, Process.name)
    ).all()

    ranked = sorted(
        [{"process_id": r[0], "workshop": r[1], "name": r[2] or f"P{r[0]}", "pending": int(r[3] or 0)} for r in rows],
        key=lambda x: x["pending"],
        reverse=True,
    )
    top = [r for r in ranked if r["pending"] >= threshold]
    return {"ok": True, "bottlenecks": top[:5], "threshold": threshold, "full_ranking": ranked[:10]}


def predict_workload(db: Session, *, days: int = 7) -> dict:
    """Predict future workshop workload using simple historical extrapolation."""
    from app.models.process import Process
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    since = date.today() - timedelta(days=days * 3)
    rows = db.execute(
        select(Process.workshop, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .join(Process, Process.id == Task.process_id)
        .where(func.date(Task.created_at) >= since)
        .group_by(Process.workshop)
    ).all()

    avg_per_day = {}
    for ws, cnt in rows:
        avg_per_day[ws] = round(int(cnt or 0) / (days * 3), 1)

    predictions = {}
    for ws, avg in avg_per_day.items():
        predictions[ws] = {
            "daily_avg": avg,
            "predicted_next_" + str(days) + "_days": round(avg * days, 1),
            "confidence": "medium" if avg > 0 else "low",
        }

    return {"ok": True, "historical_days": days * 3, "prediction_window_days": days, "predictions": predictions}