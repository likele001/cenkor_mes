"""工资明细台账：件次报工 + 历史批量报工 + 计时工资，对标 thinkmes 工资列表"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services.display_label import product_display_name, sku_display_name


STATUS_LABELS = {
    "draft": "待报",
    "submitted": "待确认",
    "leader_approved": "待确认",
    "qc_approved": "已确认",
    "rejected": "已拒绝",
}


def _status_label(raw: str) -> str:
    return STATUS_LABELS.get(raw, raw)


def _month_of(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m")


def _row_from_unit(unit: ReportUnit, salary: SalaryItem | None) -> dict:
    task = unit.task
    wo = task.work_order if task else None
    order = wo.order if wo else None
    product = wo.product if wo else None
    sku = wo.sku if wo else None
    proc = task.process if task else None
    u = unit.user
    reported_at = unit.submitted_at or unit.created_at
    month = salary.month if salary else _month_of(reported_at)
    unit_price = float(salary.unit_price) if salary else 0.0
    amount = float(salary.amount) if salary else 0.0
    if unit.status != "qc_approved":
        amount = 0.0
    pn = product_display_name(product.name, product.description, product.code, product.category) if product else ""
    sm = sku_display_name(sku.name, sku.code) if sku else ""
    return {
        "id": unit.id,
        "source": "unit",
        "salary_id": salary.id if salary else None,
        "report_unit_id": unit.id,
        "report_id": None,
        "user_id": unit.user_id,
        "username": u.username if u else None,
        "user_full_name": u.full_name if u else None,
        "order_id": order.id if order else None,
        "order_code": order.code if order else None,
        "product_id": product.id if product else None,
        "product_name": pn or (product.name if product else None),
        "sku_id": sku.id if sku else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sm or (sku.name if sku else None),
        "process_id": proc.id if proc else None,
        "process_code": proc.code if proc else None,
        "process_name": proc.name if proc else None,
        "unit_seq": unit.unit_seq,
        "reported_qty": 1,
        "unit_price": unit_price,
        "amount": amount,
        "status": unit.status,
        "status_label": _status_label(unit.status),
        "reported_at": reported_at,
        "month": month,
        "task_code": task.task_code if task else None,
        "result_type": unit.result_type,
    }


def _row_from_report(report: Report, salary: SalaryItem | None) -> dict:
    task = report.task
    wo = task.work_order if task else None
    order = wo.order if wo else None
    product = wo.product if wo else None
    sku = wo.sku if wo else None
    proc = task.process if task else None
    u = report.report_user
    reported_at = report.created_at
    month = salary.month if salary else _month_of(reported_at)
    unit_price = float(salary.unit_price) if salary else 0.0
    amount = float(salary.amount) if salary else 0.0
    if report.status != "qc_approved":
        amount = 0.0
    pn = product_display_name(product.name, product.description, product.code, product.category) if product else ""
    sm = sku_display_name(sku.name, sku.code) if sku else ""
    return {
        "id": report.id,
        "source": "report",
        "salary_id": salary.id if salary else None,
        "report_unit_id": None,
        "report_id": report.id,
        "user_id": report.report_user_id,
        "username": u.username if u else None,
        "user_full_name": u.full_name if u else None,
        "order_id": order.id if order else None,
        "order_code": order.code if order else None,
        "product_id": product.id if product else None,
        "product_name": pn or (product.name if product else None),
        "sku_id": sku.id if sku else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sm or (sku.name if sku else None),
        "process_id": proc.id if proc else None,
        "process_code": proc.code if proc else None,
        "process_name": proc.name if proc else None,
        "unit_seq": None,
        "reported_qty": int(report.good_qty),
        "unit_price": unit_price,
        "amount": amount,
        "status": report.status,
        "status_label": _status_label(report.status),
        "reported_at": reported_at,
        "month": month,
        "task_code": task.task_code if task else None,
        "result_type": None,
    }


def _load_salary_map(db: Session, *, report_unit_ids: list[int], report_ids: list[int]) -> tuple[dict[int, SalaryItem], dict[int, SalaryItem]]:
    by_unit: dict[int, SalaryItem] = {}
    by_report: dict[int, SalaryItem] = {}
    if report_unit_ids:
        rows = db.scalars(
            select(SalaryItem).where(
                SalaryItem.report_unit_id.in_(report_unit_ids),
            )
        ).all()
        for s in rows:
            if s.report_unit_id:
                by_unit[s.report_unit_id] = s
    if report_ids:
        rows = db.scalars(
            select(SalaryItem).where(
                SalaryItem.report_id.in_(report_ids),
            )
        ).all()
        for s in rows:
            if s.report_id:
                by_report[s.report_id] = s
    return by_unit, by_report


def list_salary_ledger(
    db: Session,
    *,
    month: str | None = None,
    user_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """合并件次报工与历史报工，按报工时间倒序。"""
    unit_stmt = (
        select(ReportUnit)
        .where(ReportUnit.status != "draft")
        .options(
            selectinload(ReportUnit.user),
            selectinload(ReportUnit.task).selectinload(Task.work_order).selectinload(WorkOrder.order),
            selectinload(ReportUnit.task).selectinload(Task.work_order).selectinload(WorkOrder.product),
            selectinload(ReportUnit.task).selectinload(Task.work_order).selectinload(WorkOrder.sku),
            selectinload(ReportUnit.task).selectinload(Task.process),
        )
    )
    if user_id is not None:
        unit_stmt = unit_stmt.where(ReportUnit.user_id == user_id)
    if status:
        unit_stmt = unit_stmt.where(ReportUnit.status == status)
    units = db.scalars(unit_stmt).all()

    report_stmt = (
        select(Report)
        .options(
            selectinload(Report.report_user),
            selectinload(Report.task).selectinload(Task.work_order).selectinload(WorkOrder.order),
            selectinload(Report.task).selectinload(Task.work_order).selectinload(WorkOrder.product),
            selectinload(Report.task).selectinload(Task.work_order).selectinload(WorkOrder.sku),
            selectinload(Report.task).selectinload(Task.process),
        )
    )
    if user_id is not None:
        report_stmt = report_stmt.where(Report.report_user_id == user_id)
    if status:
        report_stmt = report_stmt.where(Report.status == status)
    reports = db.scalars(report_stmt).all()

    by_unit, by_report = _load_salary_map(
        db,
        report_unit_ids=[u.id for u in units],
        report_ids=[r.id for r in reports],
    )

    rows: list[dict] = []
    for u in units:
        row = _row_from_unit(u, by_unit.get(u.id))
        if month and row["month"] != month:
            continue
        if keyword:
            kw = keyword.strip().lower()
            hay = " ".join(
                str(x or "")
                for x in [
                    row.get("order_code"),
                    row.get("product_name"),
                    row.get("sku_name"),
                    row.get("process_name"),
                    row.get("username"),
                    row.get("user_full_name"),
                    row.get("task_code"),
                ]
            ).lower()
            if kw not in hay:
                continue
        rows.append(row)

    for r in reports:
        row = _row_from_report(r, by_report.get(r.id))
        if month and row["month"] != month:
            continue
        if keyword:
            kw = keyword.strip().lower()
            hay = " ".join(
                str(x or "")
                for x in [
                    row.get("order_code"),
                    row.get("product_name"),
                    row.get("sku_name"),
                    row.get("process_name"),
                    row.get("username"),
                    row.get("user_full_name"),
                    row.get("task_code"),
                ]
            ).lower()
            if kw not in hay:
                continue
        rows.append(row)

    rows.sort(key=lambda x: x.get("reported_at") or datetime.min, reverse=True)
    total = len(rows)
    page = rows[offset : offset + limit]
    return page, total


def _row_from_hourly(salary: SalaryItem, user: User | None) -> dict:
    return {
        "id": salary.id,
        "source": "hourly",
        "salary_id": salary.id,
        "report_unit_id": None,
        "report_id": None,
        "user_id": salary.user_id,
        "username": user.username if user else None,
        "user_full_name": user.full_name if user else None,
        "order_id": None,
        "order_code": None,
        "product_id": None,
        "product_name": None,
        "sku_id": None,
        "sku_code": None,
        "sku_name": None,
        "process_id": None,
        "process_code": None,
        "process_name": None,
        "unit_seq": None,
        "reported_qty": 0,
        "unit_price": float(salary.unit_price),
        "amount": float(salary.amount),
        "status": "confirmed" if salary.item_type == "hourly" else "absent",
        "status_label": "已确认" if salary.item_type == "hourly" else "缺卡",
        "reported_at": salary.created_at,
        "month": salary.month,
        "task_code": None,
        "result_type": None,
        "work_date": salary.work_date,
        "work_hours": float(salary.work_hours) if salary.work_hours else 0,
    }


def list_hourly_ledger(
    db: Session,
    *,
    month: str | None = None,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """计时工资台账"""
    stmt = select(SalaryItem, User).join(User, User.id == SalaryItem.user_id).where(
        SalaryItem.item_type.in_(["hourly", "absent"]),
    )
    if month:
        stmt = stmt.where(SalaryItem.month == month)
    if user_id is not None:
        stmt = stmt.where(SalaryItem.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(SalaryItem.work_date.desc(), SalaryItem.user_id).offset(offset).limit(limit)
    rows = db.execute(stmt).all()

    items = [_row_from_hourly(s, u) for s, u in rows]
    return items, total
