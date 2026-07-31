"""Pricing advisor - rule-based + enhanced multi-factor analysis."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.process_price import ProcessPrice
from app.models.report import Report
from app.models.task import Task
from app.models.work_order import WorkOrder


def suggest_price_adjustments(db: Session, tenant_id: int, *, min_reports: int = 20) -> dict:
    """Rule-based price adjustment recommendation."""
    rows = db.execute(
        select(
            ProcessPrice.sku_id,
            ProcessPrice.process_id,
            ProcessPrice.unit_price,
            func.sum(Report.good_qty),
            func.count(Report.id),
        )
        .join(Task, Task.process_id == ProcessPrice.process_id)
        .join(WorkOrder, (WorkOrder.id == Task.work_order_id) & (WorkOrder.sku_id == ProcessPrice.sku_id))
        .join(Report, Report.task_id == Task.id)
        .where(WorkOrder.tenant_id == tenant_id, Report.status == "qc_approved")
        .group_by(ProcessPrice.sku_id, ProcessPrice.process_id)
    ).all()
    suggestions = []
    for sku_id, process_id, price, good_qty, report_cnt in rows:
        if report_cnt < min_reports:
            continue
        good = int(good_qty or 0)
        avg = good / report_cnt
        if avg >= 50:
            adjust = round(float(price or 0) * 1.1, 2)
            reason = "高产量(>=50/次)"
        elif avg < 15:
            adjust = round(float(price or 0) * 0.85, 2)
            reason = "低产出(<15/次)"
        else:
            continue
        suggestions.append({
            "sku_id": sku_id,
            "process_id": process_id,
            "current_price": float(price or 0),
            "suggested_price": adjust,
            "reason": reason,
            "avg_items_per_report": round(avg, 1),
            "report_count": report_cnt,
        })
    suggestions.sort(key=lambda x: x["report_count"], reverse=True)
    return {"ok": True, "analyzed": len(suggestions), "suggestions": suggestions[:20]}


def suggest_prices_enhanced(db: Session, tenant_id: int, *, min_reports: int = 10) -> dict:
    """Enhanced multi-factor pricing recommendation (L3+)."""
    try:
        from app.services.ai.pricing.enhanced_pricing import suggest_prices_enhanced as _enhanced
        return _enhanced(db, tenant_id, min_reports=min_reports)
    except Exception as e:
        return suggest_price_adjustments(db, tenant_id, min_reports=min_reports)
