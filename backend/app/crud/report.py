from datetime import datetime

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session, selectinload

from app.models.process_price import ProcessPrice
from app.models.report import Report, ReportAudit
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.work_order import WorkOrder


# ── 报工 ──

def create_report(
    db: Session,
    task_id: int,
    report_user_id: int,
    good_qty: int,
    bad_qty: int,
    remark: str | None,
    attachment_ids: str | None,
) -> Report:
    report = Report(
        task_id=task_id,
        report_user_id=report_user_id,
        good_qty=good_qty,
        bad_qty=bad_qty,
        remark=remark,
        attachment_ids=attachment_ids,
        status="submitted",
    )
    db.add(report)
    db.flush()
    return report


def get_report_by_id(db: Session, report_id: int) -> Report | None:
    return db.scalar(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.task), selectinload(Report.audits), selectinload(Report.report_user))
    )


PENDING_AUDIT_REPORT_STATUSES = ("submitted", "leader_approved")


def list_reports(
    db: Session,
    task_id: int | None = None,
    report_user_id: int | None = None,
    status: str | None = None,
    pending_audit: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Report]:
    stmt = (
        select(Report)
        .options(selectinload(Report.report_user), selectinload(Report.task))
    )
    if task_id is not None:
        stmt = stmt.where(Report.task_id == task_id)
    if report_user_id is not None:
        stmt = stmt.where(Report.report_user_id == report_user_id)
    if pending_audit:
        stmt = stmt.where(Report.status.in_(PENDING_AUDIT_REPORT_STATUSES))
    elif status:
        stmt = stmt.where(Report.status == status)
    stmt = stmt.order_by(Report.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


# ── 审核 ──

def create_audit(
    db: Session,
    report_id: int,
    auditor_id: int,
    audit_level: str,
    action: str,
    reason: str | None,
) -> ReportAudit:
    audit = ReportAudit(
        report_id=report_id,
        auditor_id=auditor_id,
        audit_level=audit_level,
        action=action,
        reason=reason,
    )
    db.add(audit)
    db.flush()
    return audit


def update_report_status(db: Session, report: Report, new_status: str) -> Report:
    report.status = new_status
    db.flush()
    return report


# ── 工资 ──

def calc_and_create_salary(
    db: Session,
    report: Report,
) -> SalaryItem | None:
    """审核通过后调用，生成工资明细"""
    task = db.get(Task, report.task_id)
    if not task:
        return None

    # 查工价
    wo = db.get(WorkOrder, task.work_order_id)
    if not wo:
        return None

    price = db.scalar(
        select(ProcessPrice).where(
            ProcessPrice.sku_id == wo.sku_id,
            ProcessPrice.process_id == task.process_id,
            ProcessPrice.is_active.is_(True),
        )
    )
    if not price:
        return None

    from decimal import Decimal
    unit_price = Decimal(str(price.unit_price))
    amount = Decimal(str(report.good_qty)) * unit_price
    month = datetime.now().strftime("%Y-%m")

    item = SalaryItem(
        report_id=report.id,
        user_id=report.report_user_id,
        sku_id=wo.sku_id,
        process_id=task.process_id,
        unit_price=unit_price,
        good_qty=report.good_qty,
        amount=amount,
        month=month,
    )
    db.add(item)
    db.flush()
    return item


def get_salary_items(
    db: Session,
    user_id: int | None = None,
    month: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[SalaryItem]:
    stmt = select(SalaryItem)
    if user_id is not None:
        stmt = stmt.where(SalaryItem.user_id == user_id)
    if month:
        stmt = stmt.where(SalaryItem.month == month)
    stmt = stmt.order_by(SalaryItem.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def get_salary_summary(
    db: Session,
    month: str | None = None,
    user_id: int | None = None,
) -> list[dict]:
    """按月/人汇总"""
    from sqlalchemy import func as sa_func

    stmt = (
        select(
            SalaryItem.user_id,
            SalaryItem.month,
            sa_func.sum(SalaryItem.amount).label("total_amount"),
            sa_func.sum(SalaryItem.good_qty).label("total_qty"),
        )
    )
    if month:
        stmt = stmt.where(SalaryItem.month == month)
    if user_id is not None:
        stmt = stmt.where(SalaryItem.user_id == user_id)
    stmt = stmt.group_by(SalaryItem.user_id, SalaryItem.month)
    stmt = stmt.order_by(SalaryItem.month.desc(), SalaryItem.user_id)
    rows = db.execute(stmt).all()
    return [
        {"user_id": r.user_id, "month": r.month, "total_amount": float(r.total_amount), "total_qty": int(r.total_qty)}
        for r in rows
    ]
