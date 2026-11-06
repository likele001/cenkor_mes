# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""不良品处置：制单 / 提交 / 审批 / 闭环

改这里之前先看清楚四条：

1. **数量额度以报工的不良量为上限**。同一报工下所有有效处置单（不含已驳回、已作废）
   的数量之和不得超过 `reports.bad_qty`。校验放在 `_assert_capacity`，建单、改单、提交
   三处都调——只在建单时校验挡不住"先建两张草稿再一起提交"。
2. **报工单是历史，不是可变状态**。闭环登记 `done_qty` 只写处置明细，
   **绝不回写 `reports.good_qty`**，否则已审核的报工、计件工资、良率全部被改写。
3. **处置单不碰库存**。报废实物出库走仓储出库单，这里只记录决定与损失金额。
   直改 `stocks.qty` 会让库存流水断链（同 `crud/stocktake.py` 的原则）。
4. **状态机单向**：draft → pending → approved → closed，
   pending 可被驳回成 rejected，rejected 可修改后重新提交；
   draft/pending/rejected 可作废，approved/closed 不可作废（决定已生效）。
"""
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.disposition import (
    DISPOSITION_METHODS,
    DISPOSITION_STATUSES,
    RELEASED_STATUSES,
    Disposition,
    DispositionItem,
)
from app.models.order import Order
from app.models.process import Process
from app.models.quality import DefectCode
from app.models.report import Report
from app.models.sku import Sku
from app.models.task import Task
from app.models.work_order import WorkOrder

_EDITABLE = ("draft", "rejected")


class DispositionStateError(ValueError):
    """处置单当前状态不允许该操作"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 序列化 ──

def _item_out(it: DispositionItem) -> dict:
    return {
        "id": it.id,
        "method": it.method,
        "qty": int(it.qty or 0),
        "defect_code_id": it.defect_code_id,
        "defect_code": it.defect_code.code if it.defect_code else None,
        "defect_name": it.defect_code.name if it.defect_code else None,
        "target_process_id": it.target_process_id,
        "target_process_name": it.target_process.name if it.target_process else None,
        "done_qty": None if it.done_qty is None else int(it.done_qty),
        "cost_amount": float(it.cost_amount or 0),
        "remark": it.remark,
    }


def disposition_out(d: Disposition, with_items: bool = True) -> dict:
    data = {
        "id": d.id,
        "code": d.code,
        "status": d.status,
        "report_id": d.report_id,
        "task_id": d.task_id,
        "work_order_id": d.work_order_id,
        "sku_id": d.sku_id,
        "sku_code": d.sku.code if d.sku else None,
        "sku_name": d.sku.name if d.sku else None,
        "process_id": d.process_id,
        "process_name": d.process.name if d.process else None,
        "task_code": d.task.task_code if d.task else None,
        "bad_qty": int(d.bad_qty or 0),
        "total_qty": int(d.total_qty or 0),
        "scrap_cost": float(d.scrap_cost or 0),
        "reason": d.reason,
        "remark": d.remark,
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "submitted_by": d.submitted_by,
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "approved_by": d.approved_by,
        "reject_reason": d.reject_reason,
        "closed_at": d.closed_at.isoformat() if d.closed_at else None,
        "closed_by": d.closed_by,
        "close_note": d.close_note,
        "created_by": d.created_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
    if with_items:
        data["items"] = [_item_out(it) for it in (d.items or [])]
    return data


# ── 查询 ──

def get_disposition(db: Session, disposition_id: int) -> Disposition | None:
    return db.scalar(
        select(Disposition)
        .where(Disposition.id == disposition_id)
        .options(
            selectinload(Disposition.items).selectinload(DispositionItem.defect_code),
            selectinload(Disposition.items).selectinload(DispositionItem.target_process),
            selectinload(Disposition.sku),
            selectinload(Disposition.process),
            selectinload(Disposition.task),
        )
    )


def _list_stmt(
    status: str | None = None,
    method: str | None = None,
    report_id: int | None = None,
    task_id: int | None = None,
    sku_id: int | None = None,
    keyword: str | None = None,
):
    stmt = select(Disposition)
    if status:
        stmt = stmt.where(Disposition.status == status)
    if method:
        stmt = stmt.where(Disposition.items.any(DispositionItem.method == method))
    if report_id is not None:
        stmt = stmt.where(Disposition.report_id == report_id)
    if task_id is not None:
        stmt = stmt.where(Disposition.task_id == task_id)
    if sku_id is not None:
        stmt = stmt.where(Disposition.sku_id == sku_id)
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Disposition.code.like(kw), Disposition.reason.like(kw)))
    return stmt


def list_dispositions(
    db: Session,
    status: str | None = None,
    method: str | None = None,
    report_id: int | None = None,
    task_id: int | None = None,
    sku_id: int | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Disposition]:
    stmt = (
        _list_stmt(status, method, report_id, task_id, sku_id, keyword)
        .options(
            selectinload(Disposition.items).selectinload(DispositionItem.defect_code),
            selectinload(Disposition.items).selectinload(DispositionItem.target_process),
            selectinload(Disposition.sku),
            selectinload(Disposition.process),
            selectinload(Disposition.task),
        )
        .order_by(Disposition.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def count_dispositions(
    db: Session,
    status: str | None = None,
    method: str | None = None,
    report_id: int | None = None,
    task_id: int | None = None,
    sku_id: int | None = None,
    keyword: str | None = None,
) -> int:
    stmt = _list_stmt(status, method, report_id, task_id, sku_id, keyword).with_only_columns(
        func.count(Disposition.id)
    )
    return int(db.scalar(stmt) or 0)


# ── 额度校验 ──

def used_qty(db: Session, report_id: int, exclude_id: int | None = None) -> int:
    """该报工下已占用的不良量（不含已驳回/已作废）。"""
    stmt = select(func.coalesce(func.sum(Disposition.total_qty), 0)).where(
        Disposition.report_id == report_id,
        Disposition.status.notin_(RELEASED_STATUSES),
    )
    if exclude_id is not None:
        stmt = stmt.where(Disposition.id != exclude_id)
    return int(db.scalar(stmt) or 0)


def _assert_capacity(db: Session, report: Report, qty: int, exclude_id: int | None = None) -> None:
    bad_qty = int(report.bad_qty or 0)
    if bad_qty <= 0:
        raise ValueError("该报工单没有不良品，无需处置")
    already = used_qty(db, report.id, exclude_id=exclude_id)
    remaining = bad_qty - already
    if qty > remaining:
        raise ValueError(
            f"超出可处置数量：报工不良 {bad_qty}，已被其他处置单占用 {already}，"
            f"本次 {qty}，最多还能处置 {max(remaining, 0)}"
        )


def _validate_method(method: str) -> str:
    if method not in DISPOSITION_METHODS:
        raise ValueError(f"不支持的处置方式：{method}")
    return method


def _clean_items(db: Session, rows: list[dict]) -> list[dict]:
    """校验并规整明细行。返回纯 dict，交给 _apply_items 落库。"""
    if not rows:
        raise ValueError("至少需要一行处置明细")
    cleaned: list[dict] = []
    for row in rows:
        method = _validate_method(str(row.get("method") or ""))
        qty = int(row.get("qty") or 0)
        if qty <= 0:
            raise ValueError("处置数量必须大于 0")
        defect_code_id = row.get("defect_code_id")
        if defect_code_id is not None:
            if not db.get(DefectCode, int(defect_code_id)):
                raise ValueError(f"缺陷代码 {defect_code_id} 不存在")
        target_process_id = row.get("target_process_id")
        if target_process_id is not None:
            if not db.get(Process, int(target_process_id)):
                raise ValueError(f"工序 {target_process_id} 不存在")
        cost = float(row.get("cost_amount") or 0)
        if cost < 0:
            raise ValueError("损失金额不能为负")
        cleaned.append({
            "method": method,
            "qty": qty,
            "defect_code_id": int(defect_code_id) if defect_code_id is not None else None,
            "target_process_id": int(target_process_id) if target_process_id is not None else None,
            "cost_amount": cost,
            "remark": row.get("remark"),
        })
    return cleaned


def _apply_items(d: Disposition, cleaned: list[dict]) -> None:
    d.items = [
        DispositionItem(
            method=row["method"],
            qty=row["qty"],
            defect_code_id=row["defect_code_id"],
            target_process_id=row["target_process_id"],
            cost_amount=row["cost_amount"],
            remark=row["remark"],
        )
        for row in cleaned
    ]
    recalc(d)


def recalc(d: Disposition) -> None:
    """按明细重算表头的数量与损失合计。明细是唯一事实来源。"""
    items = d.items or []
    d.total_qty = sum(int(it.qty or 0) for it in items)
    d.scrap_cost = sum(float(it.cost_amount or 0) for it in items if it.method == "scrap")


# ── 制单 / 改单 ──

def create_disposition(
    db: Session,
    *,
    code: str,
    report_id: int,
    items: list[dict],
    reason: str | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> Disposition:
    report = db.get(Report, int(report_id))
    if not report:
        raise ValueError("报工单不存在")
    task = db.get(Task, report.task_id)
    if not task:
        raise ValueError("报工单关联的任务不存在")
    work_order = db.get(WorkOrder, task.work_order_id) if task.work_order_id else None

    cleaned = _clean_items(db, items)
    total = sum(row["qty"] for row in cleaned)
    _assert_capacity(db, report, total)

    d = Disposition(
        code=code,
        status="draft",
        report_id=report.id,
        task_id=task.id,
        work_order_id=work_order.id if work_order else None,
        sku_id=work_order.sku_id if work_order else None,
        process_id=task.process_id,
        bad_qty=int(report.bad_qty or 0),
        reason=reason,
        remark=remark,
        created_by=created_by,
    )
    _apply_items(d, cleaned)
    db.add(d)
    db.flush()
    return d


def update_disposition(
    db: Session,
    d: Disposition,
    *,
    items: list[dict] | None = None,
    reason: str | None = None,
    remark: str | None = None,
) -> Disposition:
    if d.status not in _EDITABLE:
        raise DispositionStateError(f"处置单当前状态为 {d.status}，不允许修改")
    report = db.get(Report, d.report_id)
    if not report:
        raise ValueError("原报工单已不存在")
    if items is not None:
        cleaned = _clean_items(db, items)
        _assert_capacity(db, report, sum(row["qty"] for row in cleaned), exclude_id=d.id)
        _apply_items(d, cleaned)
        # 驳回后改单视为重新起草，避免"改了还能挂着被驳回的帽子"
        if d.status == "rejected":
            d.status = "draft"
    if reason is not None:
        d.reason = reason
    if remark is not None:
        d.remark = remark
    db.flush()
    return d


# ── 状态流转 ──

def _need(d: Disposition, allowed: tuple[str, ...], action: str) -> None:
    if d.status not in allowed:
        raise DispositionStateError(f"处置单当前状态为 {d.status}，不允许{action}")


def submit_disposition(db: Session, d: Disposition, submitted_by: int | None = None) -> Disposition:
    _need(d, ("draft", "rejected"), "提交审批")
    if not d.items:
        raise DispositionStateError("没有处置明细，无法提交")
    # 先按明细重算：表头 total_qty 只是冗余，真正的事实是明细行
    recalc(d)
    report = db.get(Report, d.report_id)
    if not report:
        raise ValueError("原报工单已不存在")
    # 提交时再校验一次：草稿堆着不动的时候，别的处置单可能已经把额度用掉了
    _assert_capacity(db, report, int(d.total_qty or 0), exclude_id=d.id)
    d.status = "pending"
    d.submitted_at = _now()
    d.submitted_by = submitted_by
    db.flush()
    return d


def approve_disposition(db: Session, d: Disposition, approved_by: int | None = None) -> Disposition:
    _need(d, ("pending",), "批准")
    d.status = "approved"
    d.approved_at = _now()
    d.approved_by = approved_by
    db.flush()
    return d


def reject_disposition(db: Session, d: Disposition, reason: str) -> Disposition:
    _need(d, ("pending",), "驳回")
    if not (reason or "").strip():
        raise ValueError("驳回必须填写原因")
    d.status = "rejected"
    d.reject_reason = reason.strip()
    db.flush()
    return d


def close_disposition(
    db: Session,
    d: Disposition,
    *,
    done_items: list[dict] | None = None,
    note: str | None = None,
    closed_by: int | None = None,
) -> Disposition:
    """闭环：登记实际执行结果。

    `done_items` 每项形如 `{item_id, done_qty, remark?}`。**未列出的明细默认视为全量执行**
    （done_qty = qty）——闭环是"这事办完了"的确认动作，逐行都要回填反而没人用；
    真有没执行完的，就把那一行显式填出来。
    """
    _need(d, ("approved",), "闭环")
    by_id = {int(it.id): it for it in (d.items or [])}
    for row in done_items or []:
        item_id = int(row["item_id"])
        it = by_id.get(item_id)
        if it is None:
            raise ValueError(f"明细行 {item_id} 不属于该处置单")
        done = int(row["done_qty"])
        if done < 0 or done > int(it.qty or 0):
            raise ValueError(f"实际执行数量必须在 0 到 {it.qty} 之间")
        it.done_qty = done
        if row.get("remark") is not None:
            it.remark = row["remark"]
    for it in (d.items or []):
        if it.done_qty is None:
            it.done_qty = int(it.qty or 0)
    d.status = "closed"
    d.closed_at = _now()
    d.closed_by = closed_by
    d.close_note = note
    db.flush()
    return d


def cancel_disposition(db: Session, d: Disposition) -> Disposition:
    if d.status in ("approved", "closed"):
        raise DispositionStateError("已批准/已闭环的处置单不能作废，处置决定已经生效")
    if d.status == "cancelled":
        raise DispositionStateError("处置单已作废")
    d.status = "cancelled"
    db.flush()
    return d


# ── 统计 ──

def disposition_stats(db: Session) -> dict:
    """按状态、处置方式、缺陷代码聚合。作废/驳回的单据不计入方式统计。"""
    status_rows = db.execute(
        select(Disposition.status, func.count(Disposition.id)).group_by(Disposition.status)
    ).all()
    by_status = {s: 0 for s in DISPOSITION_STATUSES}
    for status, cnt in status_rows:
        by_status[str(status)] = int(cnt or 0)

    method_rows = db.execute(
        select(
            DispositionItem.method,
            func.coalesce(func.sum(DispositionItem.qty), 0),
            func.coalesce(func.sum(DispositionItem.cost_amount), 0),
            func.count(DispositionItem.id),
        )
        .join(Disposition, Disposition.id == DispositionItem.disposition_id)
        .where(Disposition.status.notin_(RELEASED_STATUSES))
        .group_by(DispositionItem.method)
    ).all()
    by_method = {m: {"qty": 0, "cost": 0.0, "lines": 0} for m in DISPOSITION_METHODS}
    for method, qty, cost, lines in method_rows:
        by_method[str(method)] = {
            "qty": int(qty or 0),
            "cost": float(cost or 0),
            "lines": int(lines or 0),
        }

    defect_rows = db.execute(
        select(
            DefectCode.code,
            DefectCode.name,
            func.coalesce(func.sum(DispositionItem.qty), 0),
        )
        .join(DispositionItem, DispositionItem.defect_code_id == DefectCode.id)
        .join(Disposition, Disposition.id == DispositionItem.disposition_id)
        .where(Disposition.status.notin_(RELEASED_STATUSES))
        .group_by(DefectCode.code, DefectCode.name)
        .order_by(func.coalesce(func.sum(DispositionItem.qty), 0).desc())
        .limit(10)
    ).all()

    totals = db.execute(
        select(
            func.coalesce(func.sum(Disposition.total_qty), 0),
            func.coalesce(func.sum(Disposition.scrap_cost), 0),
        ).where(Disposition.status.notin_(RELEASED_STATUSES))
    ).one()

    return {
        "by_status": by_status,
        "by_method": by_method,
        "top_defects": [
            {"code": code, "name": name, "qty": int(qty or 0)} for code, name, qty in defect_rows
        ],
        "total_qty": int(totals[0] or 0),
        "scrap_cost": float(totals[1] or 0),
    }


# ── 可选报工（制单下拉） ──

def report_options(db: Session, keyword: str | None = None, limit: int = 50) -> list[dict]:
    """列出还有不良量可处置的报工单。

    只返回 `bad_qty > 0` 且「可处置余量 > 0」的报工——不良量已经处置完的报工再挂上去
    必然被额度校验挡回，不如直接在候选里过滤掉。
    """
    used_map = {
        int(rid): int(qty or 0)
        for rid, qty in db.execute(
            select(Disposition.report_id, func.coalesce(func.sum(Disposition.total_qty), 0))
            .where(Disposition.status.notin_(RELEASED_STATUSES))
            .group_by(Disposition.report_id)
        ).all()
    }

    stmt = (
        select(Report, Task, WorkOrder, Sku, Process, Order)
        .join(Task, Task.id == Report.task_id)
        .outerjoin(WorkOrder, WorkOrder.id == Task.work_order_id)
        .outerjoin(Sku, Sku.id == WorkOrder.sku_id)
        .outerjoin(Process, Process.id == Task.process_id)
        .outerjoin(Order, Order.id == WorkOrder.order_id)
        .where(Report.bad_qty > 0)
        .order_by(Report.id.desc())
        .limit(max(limit * 4, 100))  # 先多取一些，过滤掉已处置完的再截断
    )
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Task.task_code.like(kw), Sku.code.like(kw), Sku.name.like(kw)))

    rows: list[dict] = []
    for report, task, work_order, sku, process, order in db.execute(stmt).all():
        bad_qty = int(report.bad_qty or 0)
        already = used_map.get(int(report.id), 0)
        remaining = bad_qty - already
        if remaining <= 0:
            continue
        rows.append({
            "report_id": report.id,
            "report_status": report.status,
            "task_id": task.id,
            "task_code": task.task_code,
            "process_id": process.id if process else None,
            "process_name": process.name if process else None,
            "work_order_id": work_order.id if work_order else None,
            "order_code": order.code if order else None,
            "sku_id": sku.id if sku else None,
            "sku_code": sku.code if sku else None,
            "sku_name": sku.name if sku else None,
            "good_qty": int(report.good_qty or 0),
            "bad_qty": bad_qty,
            "used_qty": already,
            "remaining_qty": remaining,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        })
        if len(rows) >= limit:
            break
    return rows
