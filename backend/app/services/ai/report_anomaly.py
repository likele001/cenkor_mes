"""报工异常实时检测 —— 提交前毫秒级规则检查

与 /h5/ai/report/check 的 LLM 检查不同：
- 本模块是纯规则引擎，< 10ms 完成
- 在报工提交 API 中同步执行（提交前拦截）
- LLM check 是用户主动点击的可选按钮
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report_unit import ReportUnit
from app.models.report import Report
from app.models.task import Task
from app.models.task_assignment import TaskAssignment

# ===== 阈值配置 =====
DOUBLE_CLICK_SEC = 3          # < 3s → 重复提交（abnormal）
RAPID_GAP_SEC = 60            # < 60s → 太快（suspect）
BURST_WINDOW_MINUTES = 10     # 统计窗口
BURST_THRESHOLD = 20          # 窗口内 > 20 次 → suspect
BAD_RATE_WINDOW = 10          # 最近 N 件
BAD_RATE_THRESHOLD = 0.8      # 不良占比 > 80% → suspect
BATCH_QTY_RATIO = 1.5         # 批量报工数量 > 计划×1.5 → suspect


def check_report_anomaly(
    db: Session,
    tenant_id: int,
    user_id: int,
    task_id: int,
    *,
    good_qty: int = 1,
    bad_qty: int = 0,
    is_piece_mode: bool = True,
) -> dict:
    """检查报工是否异常。

    Args:
        db: DB session
        tenant_id: 租户 ID
        user_id: 报工员工 ID
        task_id: 任务 ID
        good_qty: 合格数（批量模式使用）
        bad_qty: 不良数（批量模式使用）
        is_piece_mode: 是否逐件模式

    Returns:
        {"level": "normal"|"suspect"|"abnormal",
         "reason": str,
         "detail": dict | None}
    """
    issues: list[str] = []
    detail: dict = {}

    # ── 规则 1: 双次点击 / 重复提交 ──
    last_report_time = _last_submit_time(db, tenant_id, user_id)
    if last_report_time:
        elapsed = (datetime.now() - last_report_time).total_seconds()
        detail["elapsed_seconds"] = round(elapsed, 1)
        if elapsed < DOUBLE_CLICK_SEC:
            issues.append(f"距上次报工仅 {elapsed:.0f} 秒，疑似重复提交")
            return {"level": "abnormal", "reason": "; ".join(issues), "detail": detail}

    # ── 规则 2: 报工速度过快 ──
    if last_report_time:
        elapsed = (datetime.now() - last_report_time).total_seconds()
        if elapsed < RAPID_GAP_SEC:
            issues.append(f"距上次报工仅 {elapsed:.0f} 秒，报工速度偏快")
            detail["rapid_gap"] = True

    # ── 规则 3: 短时爆发提交 ──
    burst_count = _count_recent_submits(db, tenant_id, user_id, minutes=BURST_WINDOW_MINUTES)
    detail["burst_count"] = burst_count
    if burst_count > BURST_THRESHOLD:
        issues.append(f"近{BURST_WINDOW_MINUTES}分钟报工{burst_count}次，报工频率异常")
        detail["burst"] = True

    # ── 规则 4: 不良率突增（仅 piece mode） ──
    if is_piece_mode:
        recent_bad_ratio = _recent_bad_ratio(db, tenant_id, user_id, n=BAD_RATE_WINDOW)
        if recent_bad_ratio is not None and recent_bad_ratio > BAD_RATE_THRESHOLD:
            issues.append(f"最近{BAD_RATE_WINDOW}件中不良占比{recent_bad_ratio:.0%}，请确认产品质量")
            detail["bad_ratio"] = round(recent_bad_ratio, 4)

    # ── 规则 5: 批量模式数量异常 ──
    if not is_piece_mode:
        total_qty = good_qty + bad_qty
        task = db.get(Task, task_id)
        if task and task.planned_qty > 0:
            ratio = total_qty / task.planned_qty
            detail["ratio_to_plan"] = round(ratio, 2)
            if ratio > BATCH_QTY_RATIO:
                issues.append(f"报工数量({total_qty})超过计划({task.planned_qty})的{ratio:.0%}")

    if not issues:
        return {"level": "normal", "reason": "", "detail": None}

    if any("重复提交" in s for s in issues):
        return {"level": "abnormal", "reason": "; ".join(issues), "detail": detail}

    return {"level": "suspect", "reason": "; ".join(issues), "detail": detail}


def _last_submit_time(db: Session, tenant_id: int, user_id: int) -> datetime | None:
    """查询该员工最近一次报工提交时间"""
    for model_cls, status_col in [(ReportUnit, ReportUnit.status), (Report, Report.status)]:
        # Report 没有 submitted_at，用 created_at 替代
        time_col = model_cls.submitted_at if hasattr(model_cls, "submitted_at") else model_cls.created_at
        t = db.scalar(
            select(func.max(time_col))
            .where(
                model_cls.tenant_id == tenant_id,
                model_cls.user_id == user_id if hasattr(model_cls, "user_id") else model_cls.report_user_id == user_id,
                status_col == "submitted",
                time_col.isnot(None),
            )
        )
        if t:
            return t
    return None


def _count_recent_submits(
    db: Session, tenant_id: int, user_id: int, minutes: int = 10
) -> int:
    """统计该员工最近 minutes 分钟的提交次数"""
    since = datetime.now() - timedelta(minutes=minutes)
    total = 0
    for model_cls, status_col, uid_col in [
        (ReportUnit, ReportUnit.status, ReportUnit.user_id),
        (Report, Report.status, Report.report_user_id),
    ]:
        # Report 没有 submitted_at，用 created_at 替代
        time_col = model_cls.submitted_at if hasattr(model_cls, "submitted_at") else model_cls.created_at
        n = db.scalar(
            select(func.count(model_cls.id)).where(
                model_cls.tenant_id == tenant_id,
                uid_col == user_id,
                status_col == "submitted",
                time_col.isnot(None),
                time_col >= since,
            )
        )
        total += int(n or 0)
    return total


def _recent_bad_ratio(
    db: Session, tenant_id: int, user_id: int, n: int = 10
) -> float | None:
    """该员工最近 n 次提交中不良占比（仅 ReportUnit, 逐件模式）"""
    rows = db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.tenant_id == tenant_id,
            ReportUnit.user_id == user_id,
            ReportUnit.status == "submitted",
        )
        .order_by(ReportUnit.id.desc())
        .limit(n)
    ).all()
    if not rows:
        return None
    bad = sum(1 for r in rows if r.result_type == "bad")
    return bad / len(rows)


def _batch_report_qty_for_user(
    db: Session, tenant_id: int, user_id: int, task_id: int, days: int = 30
) -> list[int]:
    """该员工近 days 天对此任务(工序)的历史报工数量"""
    since = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(Report.good_qty + Report.bad_qty)
        .where(
            Report.tenant_id == tenant_id,
            Report.report_user_id == user_id,
            Report.task_id == task_id,
            Report.status == "submitted",
            Report.created_at.isnot(None),
            Report.created_at >= since,
        )
    ).all()
    return [int(r[0]) for r in rows]
