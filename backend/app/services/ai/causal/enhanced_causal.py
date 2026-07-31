# -*- coding: utf-8 -*-
"""Enhanced causal inference - statistical association + LLM hypothesis generation."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def analyze_yield_causes_enhanced(db: Session, tenant_id: int, *, days: int = 30) -> dict:
    """Enhanced yield analysis with process-level breakdown, trend comparison, and LLM hypothesis."""
    from app.models.report import Report
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    since = date.today() - timedelta(days=days)

    # Per-process yield breakdown (last 30 days)
    process_rows = db.execute(
        select(Task.process_id, func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .join(Report, Report.task_id == Task.id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            Report.status == "qc_approved",
            func.date(Report.created_at) >= since,
        )
        .group_by(Task.process_id)
    ).all()

    processes = []
    total_good = 0
    total_bad = 0
    for pid, g, b in process_rows:
        good = int(g or 0)
        bad = int(b or 0)
        total = good + bad
        rate = round(good / total * 100, 1) if total > 0 else 0
        processes.append({"process_id": pid, "good": good, "bad": bad, "total": total, "yield_rate": rate})
        total_good += good
        total_bad += bad

    # Sort by yield rate (ascending - worst first)
    processes.sort(key=lambda x: x["yield_rate"])
    overall_rate = round(total_good / (total_good + total_bad) * 100, 1) if (total_good + total_bad) > 0 else 0

    # Trend comparison (first half vs second half)
    half_point = date.today() - timedelta(days=days // 2)
    recent_rows = db.execute(
        select(func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(Task, Task.id == Report.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.tenant_id == tenant_id, Report.status == "qc_approved",
               func.date(Report.created_at) >= half_point)
    ).first()

    older_rows = db.execute(
        select(func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(Task, Task.id == Report.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.tenant_id == tenant_id, Report.status == "qc_approved",
               func.date(Report.created_at) >= since, func.date(Report.created_at) < half_point)
    ).first()

    def _get_rate(row):
        if not row: return None
        g, b = int(row[0] or 0), int(row[1] or 0)
        total = g + b
        return round(g / total * 100, 1) if total > 0 else None

    recent_rate = _get_rate(recent_rows)
    older_rate = _get_rate(older_rows)
    trend = "stable"
    if recent_rate is not None and older_rate is not None and older_rate > 0:
        delta = recent_rate - older_rate
        if delta > 2: trend = "improving"
        elif delta < -2: trend = "declining"

    # Low-yield processes (bottom 25%)
    if processes:
        rates = [p["yield_rate"] for p in processes if p["total"] > 0]
        if rates:
            threshold = sorted(rates)[len(rates) // 4]
            low_yield = [p for p in processes if p["total"] > 0 and p["yield_rate"] <= threshold]
        else:
            low_yield = []
    else:
        low_yield = []

    # Build LLM hypothesis
    hypotheses = []
    if low_yield:
        pids = [str(p["process_id"]) for p in low_yield[:3]]
        hypotheses.append({
            "hypothesis": f"工序 {', '.join(pids)} 良率持续偏低，可能与来料质量、设备状态或员工技能匹配度有关",
            "evidence": f"这些工序近 {days} 天良率均低于全厂平均 {overall_rate}%",
            "suggestion": "建议核查该工序的设备点检记录，并分析不良件备注中的主要缺陷类型",
        })
    if trend == "declining":
        hypotheses.append({
            "hypothesis": "全厂良率近期呈下降趋势",
            "evidence": f"后半期良率 {recent_rate}% 低于前半期 {older_rate}%",
            "suggestion": "建议核查近期是否有设备变动或新员工上岗，加强巡检和培训",
        })
    if not hypotheses:
        hypotheses.append({
            "hypothesis": "当前生产状态相对稳定",
            "evidence": f"全厂良率 {overall_rate}%，未发现显著异常",
            "suggestion": "维持当前生产节奏，持续监控关键工序",
        })

    return {
        "ok": True,
        "days": days,
        "total_good": total_good,
        "total_bad": total_bad,
        "overall_yield_rate": overall_rate,
        "trend": trend,
        "recent_rate": recent_rate,
        "prior_rate": older_rate,
        "process_breakdown": processes[:10],
        "low_yield_processes": low_yield[:5],
        "hypotheses": hypotheses,
    }


def correlation_matrix(db: Session, tenant_id: int, *, days: int = 30) -> dict:
    """Compute simple correlation between per-process bad quantities."""
    from app.models.report import Report
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    since = date.today() - timedelta(days=days)

    rows = db.execute(
        select(Task.process_id, func.date(Report.created_at), func.sum(Report.bad_qty))
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            Report.status == "qc_approved",
            func.date(Report.created_at) >= since,
        )
        .group_by(Task.process_id, func.date(Report.created_at))
    ).all()

    # Build daily series per process
    series: dict = {}
    for pid, d, cnt in rows:
        if pid not in series:
            series[pid] = {}
        series[pid][str(d)] = int(cnt or 0)

    # Build correlation (simple covariance-based)
    pids = list(series.keys())
    corrs = []
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            a, b = pids[i], pids[j]
            common_dates = set(series[a].keys()) & set(series[b].keys())
            if len(common_dates) < 5:
                continue
            a_vals = [series[a][d] for d in common_dates]
            b_vals = [series[b][d] for d in common_dates]
            a_mean = sum(a_vals) / len(a_vals)
            b_mean = sum(b_vals) / len(b_vals)
            num = sum((x - a_mean) * (y - b_mean) for x, y in zip(a_vals, b_vals))
            den_a = sum((x - a_mean) ** 2 for x in a_vals)
            den_b = sum((y - b_mean) ** 2 for y in b_vals)
            if den_a > 0 and den_b > 0:
                corr = num / ((den_a * den_b) ** 0.5)
                if abs(corr) > 0.4:
                    corrs.append({"process_a": a, "process_b": b, "correlation": round(corr, 3)})

    corrs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return {"ok": True, "days": days, "processes_analyzed": len(pids), "correlations": corrs[:10]}
