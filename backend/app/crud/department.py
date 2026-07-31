from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.department import Department


def get_department_by_id(db: Session, department_id: int) -> Department | None:
    return db.scalar(select(Department).where(Department.id == department_id))


def get_department_by_code(db: Session, code: str) -> Department | None:
    return db.scalar(select(Department).where(Department.code == code))


def list_departments(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 200,
    include_inactive: bool = False,
) -> list[Department]:
    stmt = select(Department)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Department.code.like(kw), Department.name.like(kw)))
    stmt = stmt.order_by(Department.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_department(
    db: Session,
    code: str,
    name: str,
    parent_id: int | None = None,
    is_active: bool = True,
) -> Department:
    item = Department(code=code, name=name, parent_id=parent_id, is_active=is_active)
    db.add(item)
    db.flush()
    return item


def update_department(
    db: Session,
    item: Department,
    code: str | None = None,
    name: str | None = None,
    parent_id: int | None = None,
    is_active: bool | None = None,
) -> Department:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if parent_id is not None:
        item.parent_id = parent_id
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
