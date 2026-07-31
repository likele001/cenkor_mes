from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role import Role


def list_permissions(db: Session, offset: int = 0, limit: int = 500) -> list[Permission]:
    stmt = select(Permission).order_by(Permission.id.asc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def get_permission_by_id(db: Session, permission_id: int) -> Permission | None:
    return db.get(Permission, permission_id)


def get_permission_by_code(db: Session, code: str) -> Permission | None:
    return db.scalar(select(Permission).where(Permission.code == code))


def create_permission(db: Session, code: str, name: str) -> Permission:
    item = Permission(code=code, name=name)
    db.add(item)
    db.flush()
    return item


def update_permission(db: Session, item: Permission, code: str | None = None, name: str | None = None) -> Permission:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    db.flush()
    return item


def delete_permission(db: Session, item: Permission) -> None:
    db.delete(item)
    db.flush()


def list_roles(db: Session, offset: int = 0, limit: int = 200) -> list[Role]:
    stmt = select(Role).order_by(Role.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def get_role_by_id(db: Session, role_id: int) -> Role | None:
    return db.scalar(select(Role).where(Role.id == role_id))


def get_role_by_code(db: Session, code: str) -> Role | None:
    return db.scalar(select(Role).where(Role.code == code))


def create_role(db: Session, code: str, name: str) -> Role:
    item = Role(code=code, name=name)
    db.add(item)
    db.flush()
    return item


def update_role(db: Session, item: Role, code: str | None = None, name: str | None = None) -> Role:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    db.flush()
    return item


def delete_role(db: Session, item: Role) -> None:
    db.delete(item)
    db.flush()


def set_role_permissions(db: Session, role: Role, permissions: list[Permission]) -> Role:
    role.permissions = permissions
    db.flush()
    return role
