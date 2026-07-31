"""报工风险评分（Task 3 智能分流）

根据员工历史报工行为 + 本次报工特征，给出 0~100 的风险分：
- 0~19  低风险 → 可自动通过至「leader_approved」，减少班组长打扰
- 20~59 中风险 → 维持当前流程，班组长正常审
- 60~100 高风险 → 强制人工审核 + 增加提醒

评分维度（总分 100）：
  1. 历史良率（近 30 天）       25 分   不良率越低分越低
  2. 历史驳回率（近 30 天）     20 分   被驳回越多分越高
  3. 经验/入职时长              10 分   新员工分略高
  4. 报工数量合理性             15 分   超出剩余/计划分高
  5. 照片证据完整               10 分   无照片分高
  6. 不良率是否在正常范围       20 分   异常突增分高
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report_unit import ReportUnit
from app.models.report import Report
from app.models.user import User
from app.models.task import Task
from app.models.task_assignment import TaskAssignment


# ===== 阈值 =====
HISTORY_WINDOW_DAYS = 30          # 行为统计窗口
GOOD_RATE_GOOD_THRESHOLD = 0.95   # ≥95% 视为良率优良
GOOD_RATE_BAD_THRESHOLD = 0.80    # <80% 视为风险
REJECT_BAD_THRESHOLD = 0.10       # 驳回率 > 10% 视为高
TENURE_SAFE_DAYS = 90             # 入职 ≥ 90 天视为熟练
TENURE_RISK_DAYS = 30             # 入职 < 30 天视为高风险
OVER_REMAIN_RATIO = 1.5           # 报工数/剩余数 > 1.5 视为异常
MIN_HISTORY_SAMPLE = 5            # 不足 5 件历史则降权

LEVEL_LOW = "low"
LEVEL_MEDIUM = "medium"
LEVEL_HIGH = "high"


def _level_for_score(score: float) -> str:
    if score < 20:
        return LEVEL_LOW
    if score < 60:
        return LEVEL_MEDIUM
    return LEVEL_HIGH


def calculate_risk_score(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    task_id: int | None,
    good_qty: int = 0,
    bad_qty: int = 0,
    has_attachments: bool = True,
    result_type: str | None = None,
    report_unit_id: int | None = None,
) -> dict:
    """计算报工风险评分。

    Returns:
        {
          "score": float (0~100),
          "level": "low" | "medium" | "high",
          "reasons": list[str],   # 评分理由（中文）
          "breakdown": dict,      # 各维度分
          "auto_pass_eligible": bool,  # 是否建议自动通过
        }
    """
    breakdown: dict[str, float] = {}
    reasons: list[str] = []

    # ── 1. 历史良率（25 分）──
    history = _user_history(db, tenant_id=tenant_id, user_id=user_id, days=HISTORY_WINDOW_DAYS)
    total_hist = history["total"]
    if total_hist >= MIN_HISTORY_SAMPLE:
        good_rate = history["good_qty"] / max(1, history["good_qty"] + history["bad_qty"])
        if good_rate >= GOOD_RATE_GOOD_THRESHOLD:
            breakdown["history_yield"] = 0
        elif good_rate >= GOOD_RATE_BAD_THRESHOLD:
            breakdown["history_yield"] = 10
            reasons.append(f"近 {HISTORY_WINDOW_DAYS} 天良率 {good_rate:.0%}（< 95%）")
        else:
            breakdown["history_yield"] = 25
            reasons.append(f"近 {HISTORY_WINDOW_DAYS} 天良率仅 {good_rate:.0%}，明显偏低")
    else:
        breakdown["history_yield"] = 5  # 数据不足，给个保守的中性分
        reasons.append(f"历史数据不足 {MIN_HISTORY_SAMPLE} 件，按经验略加关注")

    # ── 2. 历史驳回率（20 分）──
    if total_hist >= MIN_HISTORY_SAMPLE:
        reject_rate = history["rejected"] / max(1, total_hist)
        if reject_rate == 0:
            breakdown["reject_rate"] = 0
        elif reject_rate <= REJECT_BAD_THRESHOLD:
            breakdown["reject_rate"] = 10
        else:
            breakdown["reject_rate"] = 20
            reasons.append(f"近 {HISTORY_WINDOW_DAYS} 天驳回率 {reject_rate:.0%}")
    else:
        breakdown["reject_rate"] = 0

    # ── 3. 经验/入职时长（10 分）──
    tenure_days = _user_tenure_days(db, user_id=user_id)
    if tenure_days >= TENURE_SAFE_DAYS:
        breakdown["tenure"] = 0
    elif tenure_days >= TENURE_RISK_DAYS:
        breakdown["tenure"] = 3
    else:
        breakdown["tenure"] = 10
        reasons.append(f"入职仅 {tenure_days} 天，新员工")

    # ── 4. 报工数量合理性（15 分）──
    if task_id:
        remaining = _task_remaining(db, tenant_id=tenant_id, task_id=task_id, user_id=user_id)
        submitted_now = good_qty + bad_qty
        if remaining > 0 and submitted_now > remaining * OVER_REMAIN_RATIO:
            breakdown["qty_sanity"] = 15
            reasons.append(f"本次报工 {submitted_now} 超过剩余 {remaining} 的 {OVER_REMAIN_RATIO} 倍")
        elif remaining > 0 and submitted_now > remaining:
            breakdown["qty_sanity"] = 5
            reasons.append(f"本次报工 {submitted_now} 略超剩余 {remaining}")
        else:
            breakdown["qty_sanity"] = 0

    # ── 5. 照片证据完整（10 分）──
    if has_attachments:
        breakdown["attachment"] = 0
    else:
        breakdown["attachment"] = 10
        reasons.append("未上传照片证据")

    # ── 6. 不良率突增（20 分）──
    # 比较最近 5 件 vs 历史 30 天的不良率
    recent = history.get("recent_bad_rate")
    overall_bad_rate = (
        history["bad_qty"] / max(1, history["good_qty"] + history["bad_qty"])
        if total_hist >= MIN_HISTORY_SAMPLE
        else None
    )
    if result_type == "bad" and recent is not None and overall_bad_rate is not None:
        # 本次就是不良
        if recent - overall_bad_rate > 0.20:
            breakdown["bad_rate_spike"] = 20
            reasons.append(f"近期不良占比突增 {recent:.0%}（历史 {overall_bad_rate:.0%}）")
        elif recent - overall_bad_rate > 0.10:
            breakdown["bad_rate_spike"] = 10
        else:
            breakdown["bad_rate_spike"] = 0
    else:
        breakdown["bad_rate_spike"] = 0

    score = float(sum(breakdown.values()))
    score = max(0.0, min(100.0, score))
    level = _level_for_score(score)
    auto_pass_eligible = level == LEVEL_LOW and total_hist >= MIN_HISTORY_SAMPLE

    return {
        "score": round(score, 2),
        "level": level,
        "reasons": reasons,
        "breakdown": breakdown,
        "auto_pass_eligible": auto_pass_eligible,
        "history_sample": total_hist,
    }


def _user_history(db: Session, *, tenant_id: int, user_id: int, days: int) -> dict:
    """统计员工近 days 天的报工历史。

    合并 ReportUnit + Report 两种来源（不同业务路径）。
    """
    since = datetime.now() - timedelta(days=days)
    out = {
        "total": 0,
        "good_qty": 0,
        "bad_qty": 0,
        "rejected": 0,
        "recent_bad_rate": None,
    }

    # ReportUnit 件次模式
    unit_rows = db.execute(
        select(ReportUnit.result_type, ReportUnit.status)
        .where(
            ReportUnit.tenant_id == tenant_id,
            ReportUnit.user_id == user_id,
            ReportUnit.submitted_at.isnot(None),
            ReportUnit.submitted_at >= since,
        )
        .order_by(ReportUnit.id.desc())
        .limit(200)
    ).all()
    # 统计
    recent_unit = []
    for r in unit_rows:
        rt, st = r[0], r[1]
        if rt == "good":
            out["good_qty"] += 1
        elif rt == "bad":
            out["bad_qty"] += 1
            recent_unit.append("bad")
        else:
            recent_unit.append("other")
        if st == "rejected":
            out["rejected"] += 1
        out["total"] += 1

    # Report 批量模式
    rep_rows = db.execute(
        select(Report.good_qty, Report.bad_qty, Report.status)
        .where(
            Report.tenant_id == tenant_id,
            Report.report_user_id == user_id,
            Report.created_at.isnot(None),
            Report.created_at >= since,
        )
        .order_by(Report.id.desc())
        .limit(200)
    ).all()
    for r in rep_rows:
        g, b, st = int(r[0] or 0), int(r[1] or 0), r[2]
        out["good_qty"] += g
        out["bad_qty"] += b
        out["total"] += g + b
        if st == "rejected":
            # 批量报工按"件次"算，每单记 1 次驳回
            out["rejected"] += 1

    # 最近 5 件的不良率
    last5 = recent_unit[:5]
    if last5:
        bad5 = sum(1 for x in last5 if x == "bad")
        out["recent_bad_rate"] = bad5 / len(last5)
    return out


def _user_tenure_days(db: Session, *, user_id: int) -> int:
    """计算用户入职天数（基于 user.created_at / hired_at）"""
    row = db.execute(
        select(User).where(User.id == user_id).limit(1)
    ).scalar_one_or_none()
    if not row:
        return 0
    anchor = getattr(row, "hired_at", None) or row.created_at
    if not anchor:
        return 0
    try:
        return max(0, (datetime.now() - anchor).days)
    except Exception:
        return 0


def _task_remaining(db: Session, *, tenant_id: int, task_id: int, user_id: int) -> int:
    """查询员工对某任务的剩余可报量。"""
    a = db.scalar(
        select(TaskAssignment).where(
            TaskAssignment.tenant_id == tenant_id,
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == user_id,
        )
    )
    if not a:
        return 0
    assigned = int(a.assigned_qty or 0)
    done = int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.tenant_id == tenant_id,
                ReportUnit.task_assignment_id == a.id,
                ReportUnit.status != "draft",
            )
        )
        or 0
    )
    return max(0, assigned - done)


def apply_auto_pass(
    db: Session,
    *,
    unit: ReportUnit,
    risk: dict,
    audit_user_id: int | None = None,
) -> bool:
    """如果风险评分满足自动通过条件，将 unit.status 推到 leader_approved。

    Returns: True 表示已自动通过；False 表示保持原状态。
    """
    if not risk.get("auto_pass_eligible"):
        return False
    if unit.status != "submitted":
        return False
    from app.crud.report_unit import create_unit_audit
    from app.services.approval_flow_resolver import get_status_after_approval

    unit.status = get_status_after_approval(db, unit.tenant_id, 0)
    # 记录预审结果（给班组长/终审可见）
    unit.prescreen_level = risk.get("level")
    import json

    unit.prescreen_json = json.dumps(
        {
            "score": risk.get("score"),
            "reasons": risk.get("reasons"),
            "breakdown": risk.get("breakdown"),
            "auto_pass": True,
            "history_sample": risk.get("history_sample"),
        },
        ensure_ascii=False,
    )
    unit.prescreen_at = datetime.now()
    create_unit_audit(
        db,
        tenant_id=unit.tenant_id,
        report_unit_id=unit.id,
        auditor_id=audit_user_id or 0,  # 0 代表系统自动
        audit_level="auto",
        action="auto_passed",
        reason=f"AI 自动通过：风险分 {risk.get('score')}（{risk.get('level')}）",
    )
    return True