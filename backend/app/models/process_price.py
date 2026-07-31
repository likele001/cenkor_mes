from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProcessPrice(Base):
    __tablename__ = "process_prices"
    __table_args__ = (UniqueConstraint("sku_id", "process_id", name="uq_process_prices_sku_process"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False, index=True)
    process_id: Mapped[int] = mapped_column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    sku = relationship("Sku", back_populates="prices")
    process = relationship("Process", back_populates="prices")
