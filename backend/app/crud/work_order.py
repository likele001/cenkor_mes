from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.sku import Sku
from app.models.task import Task
from app.models.work_order import WorkOrder


def get_work_order_by_id(db: Session, work_order_id: int, with_tasks: bool = False) -> WorkOrder | None:
    stmt = select(WorkOrder).where(WorkOrder.id == work_order_id)
    if with_tasks:
        stmt = stmt.options(selectinload(WorkOrder.tasks).selectinload(Task.process))
    return db.scalar(stmt)


def list_work_orders(
    db: Session,
    order_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.sku).selectinload(Sku.product),
            selectinload(WorkOrder.product),
        )
    )
    if order_id is not None:
        stmt = stmt.where(WorkOrder.order_id == order_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    stmt = stmt.order_by(WorkOrder.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()
