from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("code", name="uq_departments_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    feishu_open_department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feishu_chat_group_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wecom_department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wecom_chat_group_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dingtalk_dept_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dingtalk_chat_group_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
