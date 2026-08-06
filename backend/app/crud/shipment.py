from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.shipment import Shipment, ShipmentItem


def get_shipment(db: Session, shipment_id: int) -> Shipment | None:
    return db.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(
            selectinload(Shipment.order),
            selectinload(Shipment.items).selectinload(ShipmentItem.sku),
        )
    )


def list_shipments(
    db: Session,
    order_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Shipment]:
    stmt = select(Shipment).options(
        selectinload(Shipment.order),
        selectinload(Shipment.items).selectinload(ShipmentItem.sku),
    )
    if order_id is not None:
        stmt = stmt.where(Shipment.order_id == order_id)
    if status:
        stmt = stmt.where(Shipment.status == status)
    stmt = stmt.order_by(Shipment.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_shipment(db: Session, data: dict[str, Any]) -> Shipment:
    s = Shipment(
        order_id=data["order_id"],
        code=data["code"],
        logistics_company=data.get("logistics_company"),
        logistics_no=data.get("logistics_no"),
        remark=data.get("remark"),
        status="pending",
    )
    s.items = [
        ShipmentItem(sku_id=item["sku_id"], qty=item["qty"])
        for item in data.get("items", [])
    ]
    db.add(s)
    db.flush()
    return s


def update_shipment(db: Session, s: Shipment, **kwargs: Any) -> Shipment:
    for k, v in kwargs.items():
        setattr(s, k, v)
    db.flush()
    return s
