# -*- coding: utf-8 -*-
"""Enhanced pricing advisor - multi-factor yield, efficiency, and demand analysis."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def suggest_prices_enhanced(db: Session, tenant_id: int, *, min_reports: int = 10) -> dict:
    """Enhanced multi-factor pricing recommendation."""
    from app.models.process_price import ProcessPrice
    from app.models.report import Report
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    since = date.today() - timedelta(days=60)

    rows = db.execute(
        select(
            ProcessPrice.sku_id,
            ProcessPrice.process_id,
            ProcessPrice.unit_price,
            func.sum(Report.good_qty),
            func.count(Report.id),
            func.avg(func.date(Report.created_at)),
        )
        .join(Task, Task.process_id == ProcessPrice.process_id)
        .join(WorkOrder, (WorkOrder.id == Task.work_order_id) & (WorkOrder.sku_id == ProcessPrice.sku_id))
        .join(Report, Report.task_id == Task.id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            ProcessPrice.tenant_id == tenant_id,
            Report.status == "qc_approved",
            func.date(Report.created_at) >= since,
        )
        .group_by(ProcessPrice.sku_id, ProcessPrice.process_id)
    ).all()

    # Factory-wide baseline
    all_reports_rows = db.execute(
        select(func.sum(Report.good_qty), func.count(Report.id))
        .join(Task, Task.id == Report.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            Report.status == "qc_approved",
            func.date(Report.created_at) >= since,
        )
    ).first()

    total_good = int(all_reports_rows[0] or 0) if all_reports_rows else 0
    total_reports = int(all_reports_rows[1] or 0) if all_reports_rows else 0
    avg_items_per_report = total_good / total_reports if total_reports > 0 else 0
    baseline_yield = total_good / total_reports if total_reports > 0 else 0  # not truly rate, but baseline

    # Build suggestions
    suggestions = []
    for sku_id, process_id, price, good_qty, report_cnt, _ in rows:
        if report_cnt < min_reports:
            continue
        good = int(good_qty or 0)
        avg_per_report = good / report_cnt if report_cnt > 0 else 0

        # Efficiency factor
        efficiency = avg_per_report / avg_items_per_report if avg_items_per_report > 0 else 1.0

        # Demand/volume factor
        volume_score = min(1.0, report_cnt / 200.0)  # normalize to 1.0 max

        # Combined adjustment
        adjustment = 0.0
        reason = []
        if efficiency > 1.3:
            adjustment += 0.10
            reason.append(f"效率偏高({round(efficiency, 2)}x)")
        elif efficiency < 0.7:
            adjustment -= 0.15
            reason.append(f"效率偏低({round(efficiency, 2)}x)")
        if volume_score > 0.8:
            adjustment += 0.05
            reason.append(f"高需求({report_cnt}次)")
        elif volume_score < 0.2:
            adjustment -= 0.05
            reason.append(f"低需求({report_cnt}次)")

        if abs(adjustment) >= 0.05:
            suggestions.append({
                "sku_id": sku_id,
                "process_id": process_id,
                "current_price": float(price or 0),
                "suggested_price": round(float(price or 0) * (1 + adjustment), 2),
                "adjustment_pct": round(adjustment * 100, 1),
                "report_count": report_cnt,
                "avg_items_per_report": round(avg_per_report, 1),
                "efficiency": round(efficiency, 2),
                "volume_score": round(volume_score, 2),
                "reasons": reason,
            })

    suggestions.sort(key=lambda x: abs(x["adjustment_pct"]), reverse=True)

    return {
        "ok": True,
        "window_days": 60,
        "baseline_avg_items_per_report": round(avg_items_per_report, 1),
        "analyzed": len(suggestions),
        "price_up_count": sum(1 for s in suggestions if s["adjustment_pct"] > 0),
        "price_down_count": sum(1 for s in suggestions if s["adjustment_pct"] < 0),
        "suggestions": suggestions[:20],
    }
