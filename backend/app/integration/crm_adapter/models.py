"""crm_adapter 数据模型：连接配置（单行）+ CRM 推送进来的订单 + 产品映射表。

表在应用启动（DB_AUTO_CREATE=true）时由 Base.metadata.create_all 自动创建，
无需手写迁移。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CrmAdapterConfig(Base):
    """CRM 对接配置（单行，id 固定为 1）。"""

    __tablename__ = "crm_adapter_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    crm_base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    connection_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    api_key: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status_map_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    sign_window: Mapped[int] = mapped_column(Integer, nullable=False, server_default="300")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmInboundOrder(Base):
    """CRM 推送进来的销售订单（以 order_code 为锚点归档）。"""

    __tablename__ = "crm_inbound_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    delivery_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    mes_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmProductMap(Base):
    """CRM 产品名(+规格) -> MES 已有 SKU 的映射，用于精确对应、避免自动建占位。"""

    __tablename__ = "crm_product_maps"
    __table_args__ = (
        UniqueConstraint("crm_product_name", "crm_spec", name="uq_crm_product_maps_name_spec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crm_product_name: Mapped[str] = mapped_column(String(256), nullable=False)
    crm_spec: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    mes_product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
