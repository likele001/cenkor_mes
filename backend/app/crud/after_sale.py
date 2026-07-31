from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shipment import AfterSale, Shipment


def list_shipments_by_order(db: Session, order_id: int) -> list[Shipment]:
    stmt = (
        select(Shipment)
        .where(Shipment.order_id == order_id)
        .order_by(Shipment.created_at.desc())
    )
    return db.scalars(stmt).all()


def create_after_sale(
    db: Session,
    order_id: int,
    sale_type: str,
    reason: str | None,
    created_by: int,
) -> AfterSale:
    code = f"AS{uuid4().hex[:8].upper()}"
    item = AfterSale(
        order_id=order_id,
        code=code,
        sale_type=sale_type,
        reason=reason,
        status="pending",
        created_by=created_by,
    )
    db.add(item)
    db.flush()
    return item


def get_after_sale_by_id(db: Session, after_sale_id: int) -> AfterSale | None:
    return db.scalar(select(AfterSale).where(AfterSale.id == after_sale_id))


def list_after_sales(
    db: Session,
    order_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AfterSale]:
    stmt = select(AfterSale)
    if order_id is not None:
        stmt = stmt.where(AfterSale.order_id == order_id)
    if status:
        stmt = stmt.where(AfterSale.status == status)
    stmt = stmt.order_by(AfterSale.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_after_sale(
    db: Session,
    item: AfterSale,
    *,
    status: str | None = None,
    solution: str | None = None,
) -> AfterSale:
    if status is not None:
        item.status = status
    if solution is not None:
        item.solution = solution
    db.flush()
    return item
