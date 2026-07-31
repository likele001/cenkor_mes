from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProcessRoute(Base):
    __tablename__ = "process_routes"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_process_routes_product_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="routes")
    steps = relationship("ProcessRouteStep", back_populates="route", cascade="all, delete-orphan", order_by="ProcessRouteStep.seq")


class ProcessRouteStep(Base):
    __tablename__ = "process_route_steps"
    __table_args__ = (
        UniqueConstraint("route_id", "seq", name="uq_process_route_steps_route_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("process_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    process_id: Mapped[int] = mapped_column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)

    route = relationship("ProcessRoute", back_populates="steps")
    process = relationship("Process", back_populates="route_steps")
