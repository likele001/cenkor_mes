from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.material import Supplier


def get_supplier_by_id(db: Session, supplier_id: int) -> Supplier | None:
    return db.scalar(select(Supplier).where(Supplier.id == supplier_id))


def get_supplier_by_code(db: Session, code: str) -> Supplier | None:
    return db.scalar(select(Supplier).where(Supplier.code == code))


def list_suppliers(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[Supplier]:
    stmt = select(Supplier)
    if not include_inactive:
        stmt = stmt.where(Supplier.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Supplier.code.like(kw), Supplier.name.like(kw)))
    stmt = stmt.order_by(Supplier.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_supplier(
    db: Session,
    code: str,
    name: str,
    contact_name: str | None,
    phone: str | None,
    address: str | None,
    remark: str | None,
    is_active: bool,
) -> Supplier:
    item = Supplier(
        code=code,
        name=name,
        contact_name=contact_name,
        phone=phone,
        address=address,
        remark=remark,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def update_supplier(
    db: Session,
    item: Supplier,
    code: str | None = None,
    name: str | None = None,
    contact_name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    remark: str | None = None,
    is_active: bool | None = None,
) -> Supplier:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if contact_name is not None:
        item.contact_name = contact_name
    if phone is not None:
        item.phone = phone
    if address is not None:
        item.address = address
    if remark is not None:
        item.remark = remark
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
