"""派工：历史报工熟练度（规则统计，非 RL）"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report_unit import ReportUnit
from app.models.task import Task


def user_process_proficiency_map(
    db: Session,
    *,
    user_ids: list[int],
    process_ids: list[int],
    days: int = 90,
) -> dict[tuple[int, int], float]:
    """
    返回 (user_id, process_id) -> 熟练度得分 [0,1]。
    基于近 N 天 qc_approved 合格件次占比与完成量。
    """
    if not user_ids or not process_ids:
        return {}
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(Task.process_id, ReportUnit.user_id, ReportUnit.result_type, func.count(ReportUnit.id))
        .join(Task, Task.id == ReportUnit.task_id)
        .where(
            ReportUnit.status == "qc_approved",
            ReportUnit.user_id.in_(user_ids),
            Task.process_id.in_(process_ids),
            ReportUnit.created_at >= since,
        )
        .group_by(Task.process_id, ReportUnit.user_id, ReportUnit.result_type)
    ).all()
    agg: dict[tuple[int, int], dict[str, int]] = {}
    for pid, uid, rt, cnt in rows:
        key = (int(uid), int(pid))
        agg.setdefault(key, {"good": 0, "bad": 0})
        if rt == "good":
            agg[key]["good"] += int(cnt)
        elif rt == "bad":
            agg[key]["bad"] += int(cnt)
    out: dict[tuple[int, int], float] = {}
    for key, v in agg.items():
        total = v["good"] + v["bad"]
        if total <= 0:
            out[key] = 0.5
        else:
            ratio = v["good"] / total
            volume_bonus = min(0.2, total / 100.0)
            out[key] = min(1.0, ratio * 0.8 + volume_bonus + 0.1)
    return out
