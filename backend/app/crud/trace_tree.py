from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.process import Process
from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.trace import TraceCode
from app.models.user import User


def build_trace_tree(db: Session, product_code: str) -> dict | None:
    """根据成品码构建层级追溯树。

    层级结构:
    - 根节点: 成品码 (product_code)
    - 子节点: 各工序的追溯记录, 按 task_seq 排序
    - 孙节点: 通过 parent_trace_id 关联的子追溯码
    """
    normalized = product_code.strip().upper()

    traces = db.scalars(
        select(TraceCode)
        .where(TraceCode.product_code == normalized)
        .options(
            selectinload(TraceCode.process),
            selectinload(TraceCode.order),
            selectinload(TraceCode.sku),
            selectinload(TraceCode.report),
            selectinload(TraceCode.report_unit),
            selectinload(TraceCode.user),
            selectinload(TraceCode.piece),
            selectinload(TraceCode.parent_trace),
        )
        .order_by(
            TraceCode.task_seq.is_(None),
            TraceCode.task_seq.asc(),
            TraceCode.id.asc(),
        )
    ).all()

    if not traces:
        traces = db.scalars(
            select(TraceCode)
            .where(TraceCode.code == normalized)
            .options(
                selectinload(TraceCode.process),
                selectinload(TraceCode.order),
                selectinload(TraceCode.sku),
                selectinload(TraceCode.report),
                selectinload(TraceCode.report_unit),
                selectinload(TraceCode.user),
                selectinload(TraceCode.piece),
                selectinload(TraceCode.parent_trace),
            )
            .order_by(
                TraceCode.task_seq.is_(None),
                TraceCode.task_seq.asc(),
                TraceCode.id.asc(),
            )
        ).all()

    if not traces:
        return None

    by_id: dict[int, dict] = {}
    roots: list[dict] = []

    for tc in traces:
        node = {
            "id": tc.id,
            "code": tc.code,
            "product_code": tc.product_code,
            "task_seq": tc.task_seq,
            "qty": tc.qty,
            "remark": tc.remark,
            "created_at": tc.created_at,
            "process": {
                "id": tc.process.id,
                "code": tc.process.code,
                "name": tc.process.name,
            } if tc.process else None,
            "order": {
                "id": tc.order.id,
                "code": tc.order.code,
                "status": tc.order.status,
            } if tc.order else None,
            "sku": {
                "id": tc.sku.id,
                "code": tc.sku.code,
                "name": tc.sku.name,
            } if tc.sku else None,
            "report": {
                "id": tc.report.id,
                "good_qty": tc.report.good_qty,
                "bad_qty": tc.report.bad_qty,
                "status": tc.report.status,
            } if tc.report else None,
            "report_unit": {
                "id": tc.report_unit.id,
                "unit_seq": tc.report_unit.unit_seq,
                "result_type": tc.report_unit.result_type,
                "status": tc.report_unit.status,
            } if tc.report_unit else None,
            "user": {
                "id": tc.user.id,
                "full_name": tc.user.full_name,
                "username": tc.user.username,
            } if tc.user else None,
            "piece_no": tc.piece.piece_no if tc.piece else None,
            "children": [],
        }
        by_id[tc.id] = node

    for tc in traces:
        node = by_id[tc.id]
        if tc.parent_trace_id and tc.parent_trace_id in by_id:
            by_id[tc.parent_trace_id]["children"].append(node)
        else:
            roots.append(node)

    first = traces[0]
    return {
        "product_code": normalized,
        "order": {
            "id": first.order.id,
            "code": first.order.code,
            "status": first.order.status,
        } if first.order else None,
        "sku": {
            "id": first.sku.id,
            "code": first.sku.code,
            "name": first.sku.name,
        } if first.sku else None,
        "total_nodes": len(traces),
        "tree": roots,
    }
