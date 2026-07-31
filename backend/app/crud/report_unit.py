from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.process_price import ProcessPrice
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.work_order import WorkOrder
from app.models.order import Order

ACTIVE_UNIT_STATUSES = ("submitted", "leader_approved", "qc_approved", "step_1_approved", "step_2_approved", "step_3_approved", "step_4_approved")
PENDING_AUDIT_UNIT_STATUSES = ("submitted", "leader_approved", "step_1_approved", "step_2_approved", "step_3_approved", "step_4_approved")


def _parse_attachment_ids(raw: str | None) -> list[int]:
    if not raw or not str(raw).strip():
        return []
    out: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def sync_assignment_units(db: Session, assignment: TaskAssignment) -> None:
    """按 assigned_qty 同步 draft 槽位（unit_seq 1..N）。"""
    existing = db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.task_assignment_id == assignment.id,
        )
        .order_by(ReportUnit.unit_seq.asc())
    ).all()
    by_seq = {u.unit_seq: u for u in existing}
    n = int(assignment.assigned_qty)

    for seq in range(1, n + 1):
        if seq not in by_seq:
            db.add(
                ReportUnit(
                    task_assignment_id=assignment.id,
                    task_id=assignment.task_id,
                    user_id=assignment.user_id,
                    unit_seq=seq,
                    status="draft",
                )
            )

    for u in existing:
        if u.unit_seq > n:
            if u.status != "draft":
                raise ValueError(f"件次#{u.unit_seq}已报工或审核中，不能缩减派工数")
            db.delete(u)
    db.flush()


def count_user_reported_units(db: Session, task_id: int, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.task_id == task_id,
                ReportUnit.user_id == user_id,
                ReportUnit.status.in_(ACTIVE_UNIT_STATUSES),
            )
        )
        or 0
    )


def count_draft_units(db: Session, task_assignment_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ReportUnit.id)).where(
                ReportUnit.task_assignment_id == task_assignment_id,
                ReportUnit.status == "draft",
            )
        )
        or 0
    )


def assignment_has_non_draft_units(db: Session, task_assignment_id: int) -> bool:
    n = db.scalar(
        select(func.count(ReportUnit.id)).where(
            ReportUnit.task_assignment_id == task_assignment_id,
            ReportUnit.status != "draft",
        )
    )
    return int(n or 0) > 0


def list_units_for_assignment(
    db: Session, task_assignment_id: int
) -> list[ReportUnit]:
    return db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.task_assignment_id == task_assignment_id,
        )
        .order_by(ReportUnit.unit_seq.asc())
    ).all()


def get_unit_by_id(db: Session, unit_id: int) -> ReportUnit | None:
    return db.scalar(
        select(ReportUnit)
        .where(ReportUnit.id == unit_id)
        .options(
            selectinload(ReportUnit.task).selectinload(Task.process),
            selectinload(ReportUnit.task).selectinload(Task.work_order).selectinload(WorkOrder.sku),
            selectinload(ReportUnit.task).selectinload(Task.work_order).selectinload(WorkOrder.order),
            selectinload(ReportUnit.user),
            selectinload(ReportUnit.audits),
            selectinload(ReportUnit.task_assignment),
        )
    )


def get_next_draft_unit(db: Session, task_assignment_id: int) -> ReportUnit | None:
    return db.scalar(
        select(ReportUnit)
        .where(
            ReportUnit.task_assignment_id == task_assignment_id,
            ReportUnit.status == "draft",
        )
        .order_by(ReportUnit.unit_seq.asc())
        .limit(1)
    )


def submit_unit(
    db: Session,
    *,
    unit: ReportUnit,
    result_type: str,
    employee_attachment_ids: str,
    remark: str | None,
) -> ReportUnit:
    if unit.status != "draft":
        raise ValueError("该件次已报工，请报下一件")
    if result_type not in ("good", "bad"):
        raise ValueError("请选择合格或不良")
    if not _parse_attachment_ids(employee_attachment_ids):
        raise ValueError("请至少上传1张报工照片")

    unit.result_type = result_type
    unit.employee_attachment_ids = employee_attachment_ids
    unit.remark = remark
    unit.status = "submitted"
    unit.submitted_at = datetime.now()
    db.flush()
    return unit


def create_unit_audit(
    db: Session,
    *,
    report_unit_id: int,
    auditor_id: int,
    audit_level: str,
    action: str,
    reason: str | None,
    attachment_ids: str | None = None,
) -> ReportUnitAudit:
    audit = ReportUnitAudit(
        report_unit_id=report_unit_id,
        auditor_id=auditor_id,
        audit_level=audit_level,
        action=action,
        reason=reason,
        attachment_ids=attachment_ids,
    )
    db.add(audit)
    db.flush()
    return audit


def reset_unit_to_draft(db: Session, unit: ReportUnit) -> ReportUnit:
    unit.status = "draft"
    unit.result_type = None
    unit.employee_attachment_ids = None
    unit.qc_attachment_ids = None
    unit.remark = None
    unit.submitted_at = None
    unit.parent_trace_id = None
    unit.piece_id = None
    db.flush()
    return unit


def calc_and_create_salary_for_unit(db: Session, unit: ReportUnit) -> SalaryItem | None:
    if unit.result_type != "good":
        return None
    existing = db.scalar(
        select(SalaryItem).where(
            SalaryItem.report_unit_id == unit.id,
        )
    )
    if existing:
        return existing

    task = db.get(Task, unit.task_id)
    if not task:
        return None
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
    amount = unit_price
    month = datetime.now().strftime("%Y-%m")

    item = SalaryItem(
        report_id=None,
        report_unit_id=unit.id,
        user_id=unit.user_id,
        sku_id=wo.sku_id,
        process_id=task.process_id,
        unit_price=unit_price,
        good_qty=1,
        amount=amount,
        month=month,
    )
    db.add(item)
    db.flush()
    return item


def list_report_units(
    db: Session,
    *,
    task_id: int | None = None,
    user_id: int | None = None,
    status: str | None = None,
    prescreen_level: str | None = None,
    risk_first: bool = False,
    pending_audit: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[ReportUnit]:
    stmt = (
        select(ReportUnit)
        .options(
            selectinload(ReportUnit.user),
            selectinload(ReportUnit.task).selectinload(Task.process),
            selectinload(ReportUnit.task)
            .selectinload(Task.work_order)
            .selectinload(WorkOrder.sku),
            selectinload(ReportUnit.task)
            .selectinload(Task.work_order)
            .selectinload(WorkOrder.order),
            selectinload(ReportUnit.task_assignment),
        )
    )
    if task_id is not None:
        stmt = stmt.where(ReportUnit.task_id == task_id)
    if user_id is not None:
        stmt = stmt.where(ReportUnit.user_id == user_id)
    if pending_audit:
        stmt = stmt.where(ReportUnit.status.in_(PENDING_AUDIT_UNIT_STATUSES))
    elif status:
        stmt = stmt.where(ReportUnit.status == status)
    if prescreen_level:
        stmt = stmt.where(ReportUnit.prescreen_level == prescreen_level)
    if risk_first:
        # 高/中/低风险优先，None 排到最后
        from sqlalchemy import case

        risk_order = case(
            (ReportUnit.prescreen_level == "high", 1),
            (ReportUnit.prescreen_level == "medium", 2),
            (ReportUnit.prescreen_level == "low", 3),
            else_=4,
        )
        stmt = stmt.order_by(risk_order.asc(), ReportUnit.id.desc())
    elif pending_audit:
        stmt = stmt.order_by(ReportUnit.submitted_at.desc(), ReportUnit.id.desc())
    else:
        stmt = stmt.order_by(ReportUnit.id.desc())
    stmt = stmt.offset(offset).limit(limit)
    return db.scalars(stmt).all()
