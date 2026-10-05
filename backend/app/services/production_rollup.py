# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""生产状态与金额汇总回写（Task → WorkOrder → Order）

这些字段此前只有读没有写：老板看板的销售额/成本/准交率、看板的任务进度、
工单工时统计，全都因为没人回写而恒为 0 或恒为初始状态。
本模块是唯一写入口，报工审核、派工、订单审核都调这里。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.process import Process
from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.models.order import Order, OrderItem

ZERO = Decimal("0")

# 计入「已完成」的报工状态（终审通过）
APPROVED_REPORT_STATUSES = ("qc_approved",)
# 说明这道工序已经动过（含审核中）
ACTIVE_REPORT_STATUSES = ("submitted", "leader_approved", "qc_approved")
ACTIVE_UNIT_STATUSES = (
    "submitted", "leader_approved", "qc_approved",
    "step_1_approved", "step_2_approved", "step_3_approved", "step_4_approved",
)


# ────────────────────────── 计数 ──────────────────────────

def _approved_report_qty(db: Session, task_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(Report.good_qty), 0)).where(
                Report.task_id == task_id,
                Report.status.in_(APPROVED_REPORT_STATUSES),
            )
        )
        or 0
    )


def _has_active_report(db: Session, task_id: int) -> bool:
    n = db.scalar(
        select(func.count(Report.id)).where(
            Report.task_id == task_id,
            Report.status.in_(ACTIVE_REPORT_STATUSES),
        )
    )
    return int(n or 0) > 0


def _approved_unit_qty(db: Session, task_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.task_id == task_id,
                ReportUnit.status.in_(APPROVED_REPORT_STATUSES),
                or_(ReportUnit.result_type.is_(None), ReportUnit.result_type != "bad"),
            )
        )
        or 0
    )


def _has_active_unit(db: Session, task_id: int) -> bool:
    n = db.scalar(
        select(func.count(ReportUnit.id)).where(
            ReportUnit.task_id == task_id,
            ReportUnit.status.in_(ACTIVE_UNIT_STATUSES),
        )
    )
    return int(n or 0) > 0


def task_done_qty(db: Session, task_id: int) -> int:
    """终审通过的合格数量 = 整批报工 good_qty + 件次报工合格件数。"""
    return _approved_report_qty(db, task_id) + _approved_unit_qty(db, task_id)


def task_started(db: Session, task_id: int) -> bool:
    return _has_active_report(db, task_id) or _has_active_unit(db, task_id)


# ────────────────────────── Task ──────────────────────────

def sync_task_status(db: Session, task: Task) -> str:
    """pending → working → done（cancelled 一类的终态由人工维护，不覆盖）"""
    if task.status in ("cancelled", "closed"):
        return task.status

    planned = int(task.planned_qty or 0)
    done = task_done_qty(db, task.id)
    if planned > 0 and done >= planned:
        new = "done"
    elif done > 0 or task_started(db, task.id):
        new = "working"
    else:
        new = "pending"

    if task.status != new:
        task.status = new
        db.flush()
    return new


# ────────────────────────── WorkOrder ──────────────────────────

def _minutes_to_hours(minutes: int) -> Decimal:
    return (Decimal(int(minutes or 0)) / Decimal("60")).quantize(Decimal("0.01"))


def sync_work_order_progress(db: Session, wo: WorkOrder) -> str:
    tasks = db.scalars(select(Task).where(Task.work_order_id == wo.id)).all()
    if not tasks:
        return wo.status

    for t in tasks:
        sync_task_status(db, t)

    statuses = [t.status for t in tasks]
    if all(s == "done" for s in statuses):
        new = "done"
    elif any(s in ("working", "done") for s in statuses):
        new = "in_progress"
    else:
        new = "open"

    now = datetime.now()
    if new in ("in_progress", "done") and wo.started_at is None:
        wo.started_at = now
    if new == "done":
        if wo.finished_at is None:
            wo.finished_at = now
    else:
        wo.finished_at = None

    # 工时：标准 = 计划数 × 工序节拍；实际 = 完成数 × 工序节拍
    # 工时来自报工事实，人工终止的工单也要如实反映已发生的投入
    std_minutes = 0
    act_minutes = 0
    for t in tasks:
        rate = int(db.scalar(
            select(Process.std_minutes).where(Process.id == t.process_id)
        ) or 0)
        std_minutes += int(t.planned_qty or 0) * rate
        act_minutes += task_done_qty(db, t.id) * rate
    wo.standard_hours = _minutes_to_hours(std_minutes)
    wo.actual_hours = _minutes_to_hours(act_minutes)

    if wo.status in ("cancelled", "closed"):
        # 人工终止的工单不允许被报工复活，与 sync_task_status 同一口径
        db.flush()
        return wo.status
    if wo.status != new:
        wo.status = new
    db.flush()
    return new


# ────────────────────────── Order ──────────────────────────

def sync_order_progress(db: Session, order: Order) -> str:
    """工单全部完工 → 订单 completed + 回写实际完成时间。"""
    if order.status in ("draft", "pending_confirm", "cancelled", "shipped"):
        return order.status

    wos = db.scalars(select(WorkOrder).where(WorkOrder.order_id == order.id)).all()
    if not wos:
        return order.status

    for wo in wos:
        sync_work_order_progress(db, wo)

    # 人工终止的工单不再阻塞订单完工，否则订单永远停在生产中
    alive = [w for w in wos if w.status not in ("cancelled", "closed")]
    all_done = bool(alive) and all(w.status == "done" for w in alive)
    if all_done:
        if order.status != "completed":
            order.status = "completed"
        if order.actual_completed_at is None:
            order.actual_completed_at = max(
                (wo.finished_at for wo in wos if wo.finished_at),
                default=datetime.now(),
            )
    else:
        if order.status == "completed":
            order.status = "producing"
        order.actual_completed_at = None
    db.flush()

    _sync_plan_completion(db, order.id, all_done=all_done)
    return order.status


def _sync_plan_completion(db: Session, order_id: int, *, all_done: bool) -> None:
    from app.models.production_plan import ProductionPlan

    plans = db.scalars(
        select(ProductionPlan).where(
            ProductionPlan.order_id == order_id,
            ProductionPlan.status.in_(("planned", "in_progress")),
        )
    ).all()
    for plan in plans:
        if plan.status == "planned":
            continue  # 未下发的计划不参与完工
        plan.status = "done" if all_done else "in_progress"
    if plans:
        db.flush()


def recalc_order_amount(db: Session, order: Order) -> Decimal:
    """销售额 = Σ 明细小计（单价 × 数量）。单价由订单录入，未填即 0，不用成本冒充收入。"""
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    total = ZERO
    for it in items:
        price = Decimal(str(it.unit_price or 0))
        qty = Decimal(int(it.qty or 0))
        subtotal = (price * qty).quantize(Decimal("0.01"))
        if Decimal(str(it.subtotal or 0)) != subtotal:
            it.subtotal = subtotal
        total += subtotal
    amount = total.quantize(Decimal("0.01"))
    if Decimal(str(order.amount or 0)) != amount:
        order.amount = amount
    db.flush()
    return amount


def recalc_order_cost(db: Session, order: Order) -> Decimal:
    """订单成本 = 该订单已生成的计件工资合计（真实发生的人工成本）。"""
    task_ids = (
        select(Task.id)
        .join(WorkOrder, Task.work_order_id == WorkOrder.id)
        .where(WorkOrder.order_id == order.id)
        .subquery()
    )
    labor = db.scalar(
        select(func.coalesce(func.sum(SalaryItem.amount), 0)).where(
            SalaryItem.report_id.in_(
                select(Report.id).where(Report.task_id.in_(select(task_ids.c.id)))
            ),
        )
    )
    unit_amount = db.scalar(
        select(func.coalesce(func.sum(SalaryItem.amount), 0)).where(
            SalaryItem.report_unit_id.in_(
                select(ReportUnit.id).where(ReportUnit.task_id.in_(select(task_ids.c.id)))
            ),
        )
    )
    cost = (Decimal(str(labor or 0)) + Decimal(str(unit_amount or 0))).quantize(Decimal("0.01"))
    if Decimal(str(order.cost_amount or 0)) != cost:
        order.cost_amount = cost
    db.flush()
    return cost


# ────────────────────────── 对外入口 ──────────────────────────

def sync_after_task_change(db: Session, task_id: int) -> None:
    """报工/件次状态变化后调用：把进度一路汇总到订单。"""
    task = db.get(Task, task_id)
    if not task:
        return
    wo = db.get(WorkOrder, task.work_order_id)
    if not wo:
        return
    sync_work_order_progress(db, wo)
    order = db.get(Order, wo.order_id)
    if not order:
        return
    sync_order_progress(db, order)
    recalc_order_cost(db, order)


def sync_after_report(db: Session, report: Report) -> None:
    sync_after_task_change(db, report.task_id)


def sync_after_unit(db: Session, unit: ReportUnit) -> None:
    sync_after_task_change(db, unit.task_id)
