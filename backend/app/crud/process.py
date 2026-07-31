from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.process import Process


def get_process_by_id(db: Session, process_id: int) -> Process | None:
    return db.scalar(select(Process).where(Process.id == process_id))


def get_process_by_code(db: Session, code: str) -> Process | None:
    return db.scalar(select(Process).where(Process.code == code))


def list_processes(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
    industry_code: str | None = None,
) -> list[Process]:
    stmt = select(Process)
    if not include_inactive:
        stmt = stmt.where(Process.is_active.is_(True))
    if industry_code:
        stmt = stmt.where(Process.industry_code == industry_code)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Process.code.like(kw), Process.name.like(kw)))
    stmt = stmt.order_by(Process.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_process(
    db: Session,
    code: str,
    name: str,
    workshop: str | None,
    std_minutes: int | None,
    is_active: bool,
) -> Process:
    item = Process(code=code, name=name, workshop=workshop, std_minutes=std_minutes, is_active=is_active)
    db.add(item)
    db.flush()
    return item


def update_process(
    db: Session,
    item: Process,
    code: str | None = None,
    name: str | None = None,
    workshop: str | None = None,
    std_minutes: int | None = None,
    is_active: bool | None = None,
) -> Process:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if workshop is not None:
        item.workshop = workshop
    if std_minutes is not None:
        item.std_minutes = std_minutes
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
