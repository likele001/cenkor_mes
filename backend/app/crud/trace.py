from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.trace import TraceCode


TRACE_TASK_SEQ_ORDER = (
    TraceCode.task_seq.is_(None),
    TraceCode.task_seq.asc(),
    TraceCode.id.asc(),
)


def _make_trace_code() -> str:
    short = uuid.uuid4().hex[:8].upper()
    return f"TC{short}"


def generate_trace_code(
    db: Session,
    order_id: int,
    sku_id: int,
    process_id: int,
    user_id: int,
    *,
    product_code: str | None = None,
    work_order_id: int | None = None,
    piece_id: int | None = None,
    parent_trace_id: int | None = None,
    task_seq: int | None = None,
    report_id: int | None = None,
    report_unit_id: int | None = None,
    qty: int = 1,
    remark: str | None = None,
) -> TraceCode:
    if product_code:
        code = product_code.strip().upper()
        existing = db.scalar(
            select(TraceCode).where(
                TraceCode.piece_id == piece_id,
                TraceCode.task_seq == task_seq,
            )
        )
        if existing:
            return existing
    else:
        code = _make_trace_code()
        while db.scalar(select(TraceCode).where(TraceCode.code == code)):
            code = _make_trace_code()
    return create_trace_code(
        db,
        code,
        order_id,
        sku_id,
        process_id,
        user_id,
        product_code=product_code,
        work_order_id=work_order_id,
        piece_id=piece_id,
        parent_trace_id=parent_trace_id,
        task_seq=task_seq,
        report_id=report_id,
        report_unit_id=report_unit_id,
        qty=qty,
        remark=remark,
    )


def generate_process_trace_event(
    db: Session,
    *,
    product_code: str,
    order_id: int,
    sku_id: int,
    process_id: int,
    user_id: int,
    work_order_id: int,
    piece_id: int,
    task_seq: int,
    report_unit_id: int,
) -> TraceCode:
    code = _make_trace_code()
    while db.scalar(select(TraceCode).where(TraceCode.code == code)):
        code = _make_trace_code()
    return create_trace_code(
        db,
        code,
        order_id,
        sku_id,
        process_id,
        user_id,
        product_code=product_code,
        work_order_id=work_order_id,
        piece_id=piece_id,
        task_seq=task_seq,
        report_unit_id=report_unit_id,
        qty=1,
    )


def create_trace_code(
    db: Session,
    code: str,
    order_id: int,
    sku_id: int,
    process_id: int,
    user_id: int,
    *,
    product_code: str | None = None,
    work_order_id: int | None = None,
    piece_id: int | None = None,
    parent_trace_id: int | None = None,
    task_seq: int | None = None,
    report_id: int | None = None,
    report_unit_id: int | None = None,
    qty: int = 1,
    remark: str | None = None,
) -> TraceCode:
    trace = TraceCode(
        code=code,
        product_code=product_code or (code if code.startswith("FP") else None),
        work_order_id=work_order_id,
        piece_id=piece_id,
        parent_trace_id=parent_trace_id,
        task_seq=task_seq,
        order_id=order_id,
        sku_id=sku_id,
        process_id=process_id,
        report_id=report_id,
        report_unit_id=report_unit_id,
        user_id=user_id,
        qty=qty,
        remark=remark,
    )
    db.add(trace)
    db.flush()
    return trace


def get_trace_by_code(db: Session, code: str) -> TraceCode | None:
    normalized = code.strip().upper()
    trace = db.scalar(
        select(TraceCode)
        .where(TraceCode.code == normalized)
        .options(
            selectinload(TraceCode.order),
            selectinload(TraceCode.sku),
            selectinload(TraceCode.process),
            selectinload(TraceCode.report).selectinload(Report.audits),
            selectinload(TraceCode.report_unit).selectinload(ReportUnit.audits),
            selectinload(TraceCode.user),
            selectinload(TraceCode.piece),
            selectinload(TraceCode.parent_trace),
        )
    )
    if trace:
        return trace
    trace = db.scalar(
        select(TraceCode)
        .where(TraceCode.product_code == normalized)
        .options(
            selectinload(TraceCode.order),
            selectinload(TraceCode.sku),
            selectinload(TraceCode.process),
            selectinload(TraceCode.report).selectinload(Report.audits),
            selectinload(TraceCode.report_unit).selectinload(ReportUnit.audits),
            selectinload(TraceCode.user),
            selectinload(TraceCode.piece),
            selectinload(TraceCode.parent_trace),
        )
        .order_by(*TRACE_TASK_SEQ_ORDER)
        .limit(1)
    )
    return trace


def list_trace_codes(
    db: Session,
    order_id: int | None = None,
    sku_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[TraceCode]:
    stmt = select(TraceCode)
    if order_id is not None:
        stmt = stmt.where(TraceCode.order_id == order_id)
    if sku_id is not None:
        stmt = stmt.where(TraceCode.sku_id == sku_id)
    stmt = stmt.order_by(TraceCode.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()
