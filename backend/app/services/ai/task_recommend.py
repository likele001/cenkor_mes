"""智能报工建议 — 根据员工分配的任务 + 历史报工 + 订单交期，推荐下一步该报工的任务。

不调用 LLM，纯 SQL + Python 排序；只对返回的推荐结果做 LLM 解释（可选）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order
from app.models.process import Process
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.report_unit import ReportUnit
from app.models.work_order import WorkOrder


def get_recommended_tasks(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    top: int = 3,
) -> list[dict]:
    """获取员工当前可报工的推荐任务列表，按推荐度排序。

    评分维度：
        1. 上次报工时间（越久越靠前，避免任务遗忘）
        2. 剩余数量（剩余多优先，体现"未完成量大"）
        3. 订单交期（< 7 天的加急）
        4. 任务 seq（工序前道优先，让流程向前推）
        5. 任务状态：dispatched > in_progress > pending
    """
    # 拉取该员工所有未完成的任务派工
    stmt = (
        select(TaskAssignment)
        .where(
            TaskAssignment.tenant_id == tenant_id,
            TaskAssignment.user_id == user_id,
        )
        .options(
            selectinload(TaskAssignment.task)
            .selectinload(Task.process),
            selectinload(TaskAssignment.task).selectinload(Task.work_order).selectinload(WorkOrder.order),
        )
        .limit(100)
    )
    assignments = db.scalars(stmt).all()

    items: list[dict] = []
    now = datetime.now()
    for a in assignments:
        task: Task = a.task
        if not task or task.status == "done":
            continue

        # 计算已报工数（基于 report_unit）
        # unit 模式每个 unit_seq = 1 件；批量模式从 quantity 取
        # 这里用 unit_seq 累加作为估算
        reported = db.scalar(
            select(func.coalesce(func.sum(ReportUnit.unit_seq), 0))
            .where(
                ReportUnit.tenant_id == tenant_id,
                ReportUnit.task_assignment_id == a.id,
            )
        ) or 0
        reported_qty = int(reported)
        # 任务可能没有 unit 模式，使用 task.assigned_qty 字段直接计算
        # 实际剩余 = assigned_qty - 已报（取 max(0, x)）
        remaining = max(0, int(a.assigned_qty) - reported_qty)
        if remaining <= 0 and task.status != "in_progress":
            continue

        # 上次报工时间
        last_unit = db.scalar(
            select(ReportUnit)
            .where(
                ReportUnit.tenant_id == tenant_id,
                ReportUnit.task_assignment_id == a.id,
            )
            .order_by(ReportUnit.submitted_at.desc(), ReportUnit.id.desc())
            .limit(1)
        )
        last_report_at = last_unit.submitted_at if last_unit and last_unit.submitted_at else None

        # 订单交期
        wo = task.work_order
        order = wo.order if wo else None
        due_date = order.due_date if order else None
        days_to_due = None
        if due_date:
            days_to_due = (due_date - date.today()).days

        # 计算 score
        score = _score_task(
            last_report_at=last_report_at,
            remaining=remaining,
            days_to_due=days_to_due,
            seq=int(task.seq or 0),
            status=str(task.status or ""),
            now=now,
        )

        priority = "urgent" if (days_to_due is not None and days_to_due <= 3) else "normal"
        reason_parts = []
        if last_report_at is None:
            reason_parts.append("尚未开始报工")
        else:
            hours = (now - last_report_at).total_seconds() / 3600
            if hours >= 24:
                reason_parts.append(f"距上次报工 {int(hours // 24)} 天")
            elif hours >= 1:
                reason_parts.append(f"距上次报工 {int(hours)} 小时")
        if remaining > 0:
            reason_parts.append(f"剩 {remaining} 件")
        if days_to_due is not None and days_to_due <= 7:
            reason_parts.append(f"{days_to_due} 天后交期")

        process: Process = task.process
        items.append(
            {
                "task_id": task.id,
                "task_code": task.task_code,
                "process_name": process.name if process else None,
                "remaining_qty": remaining,
                "assigned_qty": int(a.assigned_qty),
                "reported_qty": reported_qty,
                "priority": priority,
                "last_report_at": last_report_at.isoformat() if last_report_at else None,
                "reason": " · ".join(reason_parts) or "建议继续",
                "score": round(score, 2),
                "days_to_due": days_to_due,
            }
        )

    items.sort(key=lambda x: (-float(x["score"]), -int(x["remaining_qty"])))
    return items[:top]


def _score_task(
    *,
    last_report_at: datetime | None,
    remaining: int,
    days_to_due: int | None,
    seq: int,
    status: str,
    now: datetime,
) -> float:
    """综合评分（越大越推荐）。"""
    score = 0.0
    # 上次报工时间（越久越靠前）
    if last_report_at is None:
        score += 30  # 从未报工的优先
    else:
        hours = (now - last_report_at).total_seconds() / 3600
        if hours >= 24:
            score += 25
        elif hours >= 4:
            score += 15
        elif hours >= 1:
            score += 5
    # 剩余数量
    if remaining > 0:
        score += min(remaining / 10.0, 25.0)
    # 交期临近
    if days_to_due is not None:
        if days_to_due <= 1:
            score += 30
        elif days_to_due <= 3:
            score += 20
        elif days_to_due <= 7:
            score += 10
        elif days_to_due > 30:
            score -= 5
    # 工序前道优先
    score += max(0, 10 - seq) * 0.5
    # 任务状态加成
    if status == "dispatched":
        score += 5
    elif status == "in_progress":
        score += 3
    return score
