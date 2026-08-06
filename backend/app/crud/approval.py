from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.approval import ApprovalFlow, ApprovalStep


def list_flows(db: Session, *, biz_type: str | None = None) -> list[ApprovalFlow]:
    stmt = select(ApprovalFlow).options(selectinload(ApprovalFlow.steps))
    if biz_type:
        stmt = stmt.where(ApprovalFlow.biz_type == biz_type)
    return db.scalars(stmt.order_by(ApprovalFlow.id)).all()


def get_flow(db: Session, flow_id: int) -> ApprovalFlow | None:
    return db.scalar(
        select(ApprovalFlow).where(ApprovalFlow.id == flow_id)
        .options(selectinload(ApprovalFlow.steps))
    )


def get_active_flow_for_biz(db: Session, biz_type: str) -> ApprovalFlow | None:
    return db.scalar(
        select(ApprovalFlow).where(
            ApprovalFlow.biz_type == biz_type,
            ApprovalFlow.is_active.is_(True),
        ).options(selectinload(ApprovalFlow.steps)).limit(1)
    )


def create_flow(db: Session, *, name: str, biz_type: str, is_active: bool = True) -> ApprovalFlow:
    flow = ApprovalFlow(name=name, biz_type=biz_type, is_active=is_active)
    db.add(flow)
    db.flush()
    return flow


def update_flow(db: Session, flow: ApprovalFlow, *, name: str | None = None, is_active: bool | None = None) -> ApprovalFlow:
    if name is not None:
        flow.name = name
    if is_active is not None:
        flow.is_active = is_active
    db.flush()
    return flow


def delete_flow(db: Session, flow: ApprovalFlow) -> None:
    db.delete(flow)
    db.flush()


def set_steps(db: Session, flow_id: int, steps_data: list[dict]) -> list[ApprovalStep]:
    old = db.scalars(select(ApprovalStep).where(ApprovalStep.flow_id == flow_id)).all()
    for o in old:
        db.delete(o)
    db.flush()

    items = []
    for i, s in enumerate(steps_data, 1):
        step = ApprovalStep(
            flow_id=flow_id,
            step_order=s.get("step_order", i),
            approver_role=s["approver_role"],
            is_required=s.get("is_required", True),
            can_skip=s.get("can_skip", False),
            label=s.get("label"),
        )
        db.add(step)
        items.append(step)
    db.flush()
    return items