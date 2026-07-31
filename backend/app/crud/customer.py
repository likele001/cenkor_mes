from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer


def get_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.id == customer_id))


def get_customer_by_code(db: Session, code: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.code == code))


def get_customer_by_name(db: Session, name: str) -> Customer | None:
    return db.scalar(
        select(Customer).where(
            Customer.name == name,
            Customer.is_active.is_(True),
        )
    )


def get_customer_by_user_id(db: Session, user_id: int) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.user_id == user_id))


def list_customers(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
    owner_user_id: int | None = None,
    scope_stmt=None,
) -> list[Customer]:
    stmt = select(Customer)
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if not include_inactive:
        stmt = stmt.where(Customer.is_active.is_(True))
    if owner_user_id is not None:
        stmt = stmt.where(Customer.owner_user_id == owner_user_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Customer.code.like(kw), Customer.name.like(kw)))
    stmt = stmt.order_by(Customer.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_customer(
    db: Session,
    code: str,
    name: str,
    user_id: int | None,
    contact_name: str | None,
    contact_phone: str | None,
    address: str | None,
    remark: str | None,
    is_active: bool,
    owner_user_id: int | None = None,
) -> Customer:
    item = Customer(
        code=code,
        name=name,
        user_id=user_id,
        owner_user_id=owner_user_id,
        contact_name=contact_name,
        contact_phone=contact_phone,
        address=address,
        remark=remark,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def update_customer(
    db: Session,
    item: Customer,
    code: str | None = None,
    name: str | None = None,
    user_id: int | None = None,
    owner_user_id: int | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    address: str | None = None,
    remark: str | None = None,
    is_active: bool | None = None,
) -> Customer:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if user_id is not None:
        item.user_id = user_id
    if owner_user_id is not None:
        item.owner_user_id = owner_user_id
    if contact_name is not None:
        item.contact_name = contact_name
    if contact_phone is not None:
        item.contact_phone = contact_phone
    if address is not None:
        item.address = address
    if remark is not None:
        item.remark = remark
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
