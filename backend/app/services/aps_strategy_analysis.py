# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""APS 策略对比 — 同一计划下的倒排 / 顺排 / 产能优化三种排法

纯确定性计算：只读日历、工时、交期，不依赖 LLM，独立版没有 AI 也能出结论。
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.crud.order import get_order_by_id
from app.crud.production_plan import get_plan_by_id
from app.services.planning_optimizer import (
    _get_workdays_setting,
    _is_workday,
    _shift_workdays,
    _total_minutes,
    optimize_plan_schedule,
)
from app.services.production_forecast import build_plan_forecast

DEFAULT_WORKDAY_MINUTES = 480


def _next_workday(db: Session, d: date, workdays: list[int]) -> date:
    cur = d
    for _ in range(400):
        if _is_workday(db, cur, workdays):
            return cur
        cur += timedelta(days=1)
    return d


def _score(*, start: date, end: date, due: date | None, span_days: int) -> tuple[int, list[str], list[str]]:
    today = date.today()
    pros: list[str] = []
    cons: list[str] = []
    score = 100

    if due:
        slack = (due - end).days
        if slack < 0:
            score -= min(60, 12 * (-slack))
            cons.append(f"预计 {end.isoformat()} 完工，超交期 {-slack} 天")
        elif slack == 0:
            score -= 15
            cons.append("恰好卡交期，无缓冲")
        else:
            pros.append(f"交期前 {slack} 天完工，有缓冲")
            score -= 0 if slack <= 10 else 8
    else:
        cons.append("订单未设交期，无法评估准交")
        score -= 20

    if start < today:
        score -= 10
        cons.append(f"需从 {start.isoformat()} 起排，早于今日")
    else:
        pros.append(f"{start.isoformat()} 起排，可立即执行")

    if span_days <= 0:
        score -= 5
        cons.append("工期为 0，按最少 1 个工作日处理")
    elif span_days > 60:
        score -= 10
        cons.append(f"工期 {span_days} 天偏长，占用产能久")

    return max(0, min(100, score)), pros, cons


def analyze_aps_strategies(db: Session, plan_id: int, user_id: int | None = None) -> dict:
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("计划不存在")
    order = get_order_by_id(db, plan.order_id, with_items=False)
    if not order:
        raise ValueError("订单不存在")

    due: date | None = order.due_date or plan.end_date
    workdays = _get_workdays_setting(db)
    total_mins = _total_minutes(db, plan.order_id)
    if total_mins <= 0:
        total_mins = int(plan.work_days or 1) * DEFAULT_WORKDAY_MINUTES
    span = max(1, (total_mins + DEFAULT_WORKDAY_MINUTES - 1) // DEFAULT_WORKDAY_MINUTES)
    if plan.work_days and int(plan.work_days) > 0:
        span = max(span, int(plan.work_days))

    strategies: list[dict] = []

    # ── 1. 倒排：锁定交期往回推 ──
    if due:
        b_end = due if _is_workday(db, due, workdays) else _shift_workdays(db, due, -1, workdays)
        b_start = _shift_workdays(db, b_end, -(span - 1), workdays)
        b_score, b_pros, b_cons = _score(start=b_start, end=b_end, due=due, span_days=span)
        b_pros.insert(0, "以交付为锚点，最大化准备时间")
        strategies.append({
            "key": "backward",
            "title": "交期倒排",
            "score": b_score,
            "start_date": b_start.isoformat(),
            "end_date": b_end.isoformat(),
            "work_days": span,
            "pros": b_pros,
            "cons": b_cons,
        })
    else:
        strategies.append({
            "key": "backward",
            "title": "交期倒排",
            "score": 0,
            "start_date": None,
            "end_date": None,
            "work_days": None,
            "pros": [],
            "cons": ["订单未设置交期，倒排不可用"],
        })

    # ── 2. 顺排：从最近的开工日往前推 ──
    f_start = _next_workday(db, date.today(), workdays)
    f_end = _shift_workdays(db, f_start, span - 1, workdays)
    f_score, f_pros, f_cons = _score(start=f_start, end=f_end, due=due, span_days=span)
    f_pros.insert(0, "尽早开工，问题暴露得早")
    strategies.append({
        "key": "forward",
        "title": "今日顺排",
        "score": f_score,
        "start_date": f_start.isoformat(),
        "end_date": f_end.isoformat(),
        "work_days": span,
        "pros": f_pros,
        "cons": f_cons,
    })

    # ── 3. 产能优化：交给排产求解器（无 OR-Tools 时走规则倒排） ──
    opt = optimize_plan_schedule(db, plan_id)
    if opt.get("ok"):
        o_start = date.fromisoformat(str(opt["suggest_start_date"])[:10])
        o_end = date.fromisoformat(str(opt["suggest_end_date"])[:10])
        o_span = int(opt.get("suggest_work_days") or span)
        o_score, o_pros, o_cons = _score(start=o_start, end=o_end, due=due, span_days=o_span)
        o_pros.insert(0, f"由 {opt.get('solver') or 'rule'} 求解，已计入日历产能")
        strategies.append({
            "key": "optimized",
            "title": "产能优化",
            "score": o_score,
            "start_date": o_start.isoformat(),
            "end_date": o_end.isoformat(),
            "work_days": o_span,
            "pros": o_pros,
            "cons": o_cons,
        })
    else:
        strategies.append({
            "key": "optimized",
            "title": "产能优化",
            "score": 0,
            "start_date": None,
            "end_date": None,
            "work_days": None,
            "pros": [],
            "cons": [opt.get("error") or "排产优化不可用"],
        })

    strategies.sort(key=lambda s: s["score"], reverse=True)
    recommended = strategies[0]["key"] if strategies and strategies[0]["score"] > 0 else ""
    forecast = build_plan_forecast(db, plan_id)

    return {
        "plan_id": plan.id,
        "plan_code": plan.code,
        "order_id": order.id,
        "order_code": order.code,
        "due_date": due.isoformat() if due else None,
        "total_minutes": total_mins,
        "strategies": strategies,
        "recommended": recommended,
        "llm_summary": None,
        "forecast": forecast,
    }
