from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserWechatSubscription(Base):
    __tablename__ = "user_wechat_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_code: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)

    accept_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "event_code", "template_id", name="uq_user_event_template"),
        Index("ix_user_wechat_subs_tenant_user", "tenant_id", "user_id"),
    )
