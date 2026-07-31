from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.role import Role
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_tenant_and_username(db: Session, username: str) -> User | None:
    return get_user_by_username(db, username)


def list_users(
    db: Session,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[User]:
    from sqlalchemy import or_

    stmt = select(User)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.like(kw), User.full_name.like(kw)))
    stmt = stmt.order_by(User.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_user(db: Session, username: str, password: str, **kwargs) -> User:
    user = User(username=username, password_hash=hash_password(password), **kwargs)
    db.add(user)
    db.flush()
    return user


def set_user_roles(db: Session, user: User, roles: list[Role]) -> User:
    user.roles = roles
    db.flush()
    return user


def update_user(
    db: Session,
    user: User,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
    is_superuser: bool | None = None,
    department_id: int | None = None,
    salary_type: str | None = None,
    hourly_rate: Decimal | float | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    if email is not None:
        user.email = email
    if is_active is not None:
        user.is_active = is_active
    if is_superuser is not None:
        user.is_superuser = is_superuser
    if department_id is not None:
        user.department_id = department_id
    if salary_type is not None:
        user.salary_type = salary_type
    if hourly_rate is not None:
        user.hourly_rate = Decimal(str(hourly_rate))
    db.flush()
    return user


def update_user_profile(db: Session, user: User, **fields: str | None) -> User:
    allowed = {"full_name", "phone", "email"}
    for key, value in fields.items():
        if key in allowed:
            setattr(user, key, value)
    db.flush()
    return user


def change_user_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise ValueError("原密码不正确")
    set_password(db, user, new_password)


def set_password(db: Session, user: User, password: str) -> User:
    user.password_hash = hash_password(password)
    db.flush()
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
