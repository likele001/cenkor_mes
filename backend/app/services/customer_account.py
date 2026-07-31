"""客户档案与 H5 登录账号绑定"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.user import create_user, get_user_by_tenant_and_username, set_user_roles
from app.models.customer import Customer
from app.models.role import Role
from app.models.user import User


def get_customer_role(db: Session) -> Role | None:
    return db.scalar(select(Role).where(Role.code == "customer"))


def ensure_customer_login_user(
    db: Session,
    customer: Customer,
    *,
    user_id: int | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> int | None:
    """
    绑定或创建客户登录用户。优先级：显式 user_id > login_username+password 新建。
    返回最终 user_id（可能为 None）。
    """
    if user_id is not None:
        u = db.get(User, user_id)
        if not u:
            raise HTTPException(status_code=400, detail="绑定用户不存在")
        other = db.scalar(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.id != customer.id,
            )
        )
        if other:
            raise HTTPException(status_code=400, detail=f"用户已被客户「{other.name}」占用")
        customer.user_id = user_id
        db.flush()
        return user_id

    username = (login_username or "").strip()
    password = (login_password or "").strip()
    if not username:
        return customer.user_id

    role = get_customer_role(db)
    if not role:
        raise HTTPException(status_code=400, detail="未配置 customer 角色，请先初始化权限")

    existing = get_user_by_tenant_and_username(db, username)
    if existing:
        other = db.scalar(
            select(Customer).where(
                Customer.user_id == existing.id,
                Customer.id != customer.id,
            )
        )
        if other:
            raise HTTPException(status_code=400, detail=f"登录名「{username}」已被其他客户占用")
        set_user_roles(db, existing, [role])
        customer.user_id = existing.id
        if password:
            from app.core.security import hash_password

            existing.password_hash = hash_password(password)
        db.flush()
        return existing.id

    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="新建登录账号时密码至少 6 位")

    u = create_user(
        db,
        username=username,
        password=password,
        full_name=customer.name,
    )
    set_user_roles(db, u, [role])
    customer.user_id = u.id
    db.flush()
    return u.id
