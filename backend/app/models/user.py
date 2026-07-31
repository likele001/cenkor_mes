from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Table, UniqueConstraint, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wx_miniapp_openid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    feishu_open_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    feishu_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feishu_union_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feishu_bound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    wecom_userid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    wecom_bound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dingtalk_userid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dingtalk_union_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dingtalk_bound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    salary_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="piece")
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    roles = relationship("Role", secondary="user_roles", back_populates="users")
    department = relationship("Department")

    @property
    def tenant_id(self) -> int:
        """单用户版固定返回 tenant_id=1"""
        return 1

