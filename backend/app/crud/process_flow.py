"""工序流转：派工预赋成品码，逐件模式按套号池动态领套"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.process import Process
from app.models.report_unit import ReportUnit
from app.models.task import Task
from app.models.trace import TraceCode
from app.crud.trace import TRACE_TASK_SEQ_ORDER
from app.models.work_order import WorkOrder
from app.models.work_order_piece import WorkOrderPiece
from app.services.report_mode_settings import get_default_report_mode, use_unit_report_mode

ACTIVE_UNIT_STATUSES = ("submitted", "leader_approved", "qc_approved")


def get_min_task_seq(db: Session, work_order_id: int) -> int:
    v = db.scalar(
        select(func.min(Task.seq)).where(Task.work_order_id == work_order_id)
    )
    return int(v or 1)


def is_first_process_task(db: Session, task: Task) -> bool:
    return int(task.seq) == get_min_task_seq(db, task.work_order_id)


def get_prev_process_task(db: Session, task: Task) -> Task | None:
    return db.scalar(
        select(Task)
        .where(
            Task.work_order_id == task.work_order_id,
            Task.seq < task.seq,
        )
        .order_by(Task.seq.desc())
        .limit(1)
    )


def get_first_process_task(db: Session, work_order_id: int) -> Task | None:
    min_seq = get_min_task_seq(db, work_order_id)
    return db.scalar(
        select(Task).where(
            Task.work_order_id == work_order_id,
            Task.seq == min_seq,
        )
    )


def list_pieces_for_work_order(db: Session, work_order_id: int) -> list[WorkOrderPiece]:
    return db.scalars(
        select(WorkOrderPiece)
        .where(WorkOrderPiece.work_order_id == work_order_id)
        .order_by(WorkOrderPiece.piece_no.asc())
    ).all()


def ensure_work_order_piece_pool(db: Session, work_order_id: int, qty: int) -> list[WorkOrderPiece]:
    """首道工序派工后预建套号池并赋成品码（status=reserved）。"""
    qty = max(0, int(qty))
    result: list[WorkOrderPiece] = []
    for piece_no in range(1, qty + 1):
        piece = get_or_create_piece(db, work_order_id, piece_no)
        if not piece.product_code:
            assign_product_code_on_piece(db, piece)
        if piece.status not in ("void", "completed"):
            first_task = get_first_process_task(db, work_order_id)
            if first_task and _task_has_qc_approved_good(db, first_task.id, piece.id):
                pass
            else:
                piece.status = "reserved"
        db.flush()
        result.append(piece)
    return result


def _task_has_piece_claim(
    db: Session,
    task_id: int,
    piece_id: int,
    *,
    exclude_unit_id: int = 0,
) -> bool:
    """本任务上是否已有报工槽位占用该套（含提交前刚绑定的 draft）。"""
    n = db.scalar(
        select(func.count(ReportUnit.id)).where(
            ReportUnit.task_id == task_id,
            ReportUnit.piece_id == piece_id,
            ReportUnit.id != exclude_unit_id,
        )
    )
    return int(n or 0) > 0


def _task_has_qc_approved_good(
    db: Session, task_id: int, piece_id: int
) -> bool:
    n = db.scalar(
        select(func.count(ReportUnit.id)).where(
            ReportUnit.task_id == task_id,
            ReportUnit.piece_id == piece_id,
            ReportUnit.status == "qc_approved",
            ReportUnit.result_type == "good",
        )
    )
    return int(n or 0) > 0


def _work_order_has_qc_approved_good(
    db: Session, work_order_id: int, piece_id: int
) -> bool:
    first_task = get_first_process_task(db, work_order_id)
    if not first_task:
        return False
    return _task_has_qc_approved_good(db, first_task.id, piece_id)


def piece_display_label(piece: WorkOrderPiece | None) -> str | None:
    if not piece:
        return None
    if piece.product_code:
        return f"第{piece.piece_no}套 · {piece.product_code}"
    return f"第{piece.piece_no}套"


def _is_piece_available_for_task(
    db: Session,
    task: Task,
    piece: WorkOrderPiece,
    *,
    exclude_unit_id: int = 0,
) -> bool:
    if piece.status == "void":
        return False
    if _task_has_piece_claim(db, task.id, piece.id, exclude_unit_id=exclude_unit_id):
        return False
    if _task_has_qc_approved_good(db, task.id, piece.id):
        return False

    first = is_first_process_task(db, task)
    if first:
        return True

    if not piece.product_code:
        return False
    prev_task = get_prev_process_task(db, task)
    if not prev_task:
        return False
    return _task_has_qc_approved_good(db, prev_task.id, piece.id)


def count_available_pieces_for_task(db: Session, task: Task) -> int:
    if not use_unit_report_mode(db):
        return 0
    wo = db.get(WorkOrder, task.work_order_id)
    if not wo:
        return 0
    ensure_work_order_piece_pool(db, wo.id, wo.qty)
    return sum(
        1
        for piece in list_pieces_for_work_order(db, wo.id)
        if _is_piece_available_for_task(db, task, piece)
    )


def claim_next_piece_for_task(
    db: Session, task: Task, unit: ReportUnit
) -> WorkOrderPiece:
    """从工单套号池领取下一套（按 piece_no 升序，谁有空谁做）。"""
    wo = db.get(WorkOrder, task.work_order_id)
    if not wo:
        raise ValueError("工单不存在")
    ensure_work_order_piece_pool(db, wo.id, wo.qty)

    if unit.piece_id:
        piece = db.get(WorkOrderPiece, unit.piece_id)
        if piece and _is_piece_available_for_task(
            db, task, piece, exclude_unit_id=unit.id
        ):
            return piece
        unit.piece_id = None
        db.flush()

    for piece in list_pieces_for_work_order(db, wo.id):
        if _is_piece_available_for_task(db, task, piece, exclude_unit_id=unit.id):
            unit.piece_id = piece.id
            db.flush()
            return piece

    first = is_first_process_task(db, task)
    if first:
        raise ValueError("暂无可领取的套号，请确认工单套数已满或联系班组长")
    prev_task = get_prev_process_task(db, task)
    prev_proc = db.get(Process, prev_task.process_id) if prev_task else None
    name = prev_proc.name if prev_proc else "上道工序"
    raise ValueError(f"暂无可报工的套号，请确认{name}已终审通过")


def void_piece_if_bad_first_process(
    db: Session, unit: ReportUnit, task: Task
) -> None:
    if unit.result_type != "bad" or not unit.piece_id:
        return
    if not is_first_process_task(db, task):
        return
    piece = db.get(WorkOrderPiece, unit.piece_id)
    if piece:
        piece.status = "void"
        db.flush()


def get_flow_context_for_task(db: Session, task: Task) -> dict:
    first = is_first_process_task(db, task)
    prev_task = None if first else get_prev_process_task(db, task)
    prev_proc = db.get(Process, prev_task.process_id) if prev_task else None
    unit_mode = use_unit_report_mode(db)
    wo = db.get(WorkOrder, task.work_order_id)
    pool_total = int(wo.qty) if wo and unit_mode else 0
    pool_available = count_available_pieces_for_task(db, task) if unit_mode else 0
    return {
        "is_first_process": first,
        "requires_parent_trace": False,
        "auto_bind_piece": unit_mode and not first,
        "piece_pool_enabled": unit_mode,
        "pool_total": pool_total,
        "pool_available": pool_available,
        "report_mode": get_default_report_mode(db),
        "prev_process_id": prev_task.process_id if prev_task else None,
        "prev_process_name": prev_proc.name if prev_proc else None,
        "current_task_seq": int(task.seq),
    }


def _make_product_code(work_order_id: int, piece_no: int) -> str:
    short = uuid.uuid4().hex[:6].upper()
    return f"FP{work_order_id:06d}{piece_no:04d}{short}"


def get_piece_by_wo_and_no(
    db: Session, work_order_id: int, piece_no: int
) -> WorkOrderPiece | None:
    return db.scalar(
        select(WorkOrderPiece).where(
            WorkOrderPiece.work_order_id == work_order_id,
            WorkOrderPiece.piece_no == piece_no,
        )
    )


def get_or_create_piece(db: Session, work_order_id: int, piece_no: int) -> WorkOrderPiece:
    piece = get_piece_by_wo_and_no(db, work_order_id, piece_no)
    if piece:
        return piece
    piece = WorkOrderPiece(
        work_order_id=work_order_id,
        piece_no=piece_no,
        status="in_progress",
    )
    db.add(piece)
    db.flush()
    return piece


def assign_product_code_on_piece(db: Session, piece: WorkOrderPiece) -> str:
    if piece.product_code:
        return piece.product_code
    code = _make_product_code(piece.work_order_id, piece.piece_no)
    while db.scalar(
        select(WorkOrderPiece.id).where(
            WorkOrderPiece.product_code == code,
        )
    ):
        code = _make_product_code(piece.work_order_id, piece.piece_no)
    piece.product_code = code
    db.flush()
    return code


def _prev_process_unit_done(
    db: Session, prev_task: Task, piece_id: int
) -> ReportUnit | None:
    return db.scalar(
        select(ReportUnit)
        .where(
            ReportUnit.task_id == prev_task.id,
            ReportUnit.piece_id == piece_id,
            ReportUnit.status == "qc_approved",
            ReportUnit.result_type == "good",
        )
        .order_by(ReportUnit.id.desc())
        .limit(1)
    )


def auto_bind_piece_to_unit(db: Session, unit: ReportUnit, task: Task) -> WorkOrderPiece:
    """逐件模式：从套号池动态领取下一套并绑定。"""
    if not use_unit_report_mode(db):
        return get_or_create_piece(db, task.work_order_id, unit.unit_seq)
    return claim_next_piece_for_task(db, task, unit)


def ensure_unit_piece_on_qc_approve(
    db: Session,
    unit: ReportUnit,
    task: Task,
    wo: WorkOrder,
) -> tuple[int, str]:
    """终审：确认套号与成品码，更新件次状态（仅逐件模式）。返回 (piece_id, product_code)。"""
    if not use_unit_report_mode(db):
        return 0, ""
    if unit.piece_id:
        piece = db.get(WorkOrderPiece, unit.piece_id)
    else:
        piece = get_or_create_piece(db, wo.id, unit.unit_seq)
        unit.piece_id = piece.id

    if not piece or piece.work_order_id != wo.id:
        raise ValueError("套号绑定异常，请重新报工")

    if not piece.product_code:
        assign_product_code_on_piece(db, piece)
    product_code = piece.product_code or ""
    if not product_code:
        raise ValueError("成品码生成失败，请联系管理员")

    piece.last_process_id = task.process_id
    piece.status = "in_progress"
    db.flush()
    return piece.id, product_code


def update_piece_after_process(db: Session, piece: WorkOrderPiece, process_id: int) -> None:
    piece.last_process_id = process_id
    db.flush()


def get_piece_by_product_code(db: Session, code: str) -> WorkOrderPiece | None:
    normalized = code.strip().upper()
    return db.scalar(
        select(WorkOrderPiece)
        .where(WorkOrderPiece.product_code == normalized)
        .options(selectinload(WorkOrderPiece.work_order))
    )


def list_flow_traces_by_piece(db: Session, piece_id: int) -> list[TraceCode]:
    return db.scalars(
        select(TraceCode)
        .where(TraceCode.piece_id == piece_id)
        .options(
            selectinload(TraceCode.process),
            selectinload(TraceCode.user),
            selectinload(TraceCode.report_unit),
        )
        .order_by(*TRACE_TASK_SEQ_ORDER)
    ).all()


def build_flow_chain_rows(db: Session, piece: WorkOrderPiece | None, trace: TraceCode) -> list[dict]:
    product_code = (piece.product_code if piece else None) or trace.product_code
    if not trace.piece_id:
        proc = db.get(Process, trace.process_id)
        return [
            {
                "product_code": product_code or trace.code,
                "trace_code": trace.code,
                "task_seq": trace.task_seq,
                "process_id": trace.process_id,
                "process_name": proc.name if proc else None,
                "user_id": trace.user_id,
                "username": None,
                "user_full_name": None,
                "report_unit_id": trace.report_unit_id,
                "created_at": trace.created_at,
            }
        ]

    traces = list_flow_traces_by_piece(db, trace.piece_id)
    rows = []
    for t in traces:
        rows.append(
            {
                "product_code": product_code or t.product_code,
                "trace_code": t.code if t.code != product_code else product_code,
                "task_seq": t.task_seq,
                "process_id": t.process_id,
                "process_name": t.process.name if t.process else None,
                "user_id": t.user_id,
                "username": t.user.username if t.user else None,
                "user_full_name": t.user.full_name if t.user else None,
                "report_unit_id": t.report_unit_id,
                "created_at": t.created_at,
            }
        )
    return rows
