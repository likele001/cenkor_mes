from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.product import Product


def get_product_by_id(db: Session, product_id: int) -> Product | None:
    return db.scalar(select(Product).where(Product.id == product_id))


def get_product_by_code(db: Session, code: str) -> Product | None:
    return db.scalar(select(Product).where(Product.code == code))


def get_product_by_name(db: Session, name: str) -> Product | None:
    return db.scalar(
        select(Product).where(
            Product.name == name,
            Product.is_active.is_(True),
        )
    )


def list_products(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[Product]:
    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Product.code.like(kw), Product.name.like(kw)))
    stmt = stmt.order_by(Product.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_product(
    db: Session,
    code: str,
    name: str,
    category: str | None,
    unit: str | None,
    description: str | None,
    is_active: bool,
) -> Product:
    item = Product(
        code=code,
        name=name,
        category=category,
        unit=unit,
        description=description,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def update_product(
    db: Session,
    item: Product,
    code: str | None = None,
    name: str | None = None,
    category: str | None = None,
    unit: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> Product:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if category is not None:
        item.category = category
    if unit is not None:
        item.unit = unit
    if description is not None:
        item.description = description
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
