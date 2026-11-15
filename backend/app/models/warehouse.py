# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Warehouse(Base):
    """仓库"""
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("code", name="uq_warehouses_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Stock(Base):
    """库存"""
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "sku_id", name="uq_stocks_warehouse_sku"),
        # 库存不能为负：应用层 adjust_stock 已拦一道，但补数脚本和并发出库会绕过它
        CheckConstraint("qty >= 0", name="ck_stocks_qty_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse")
    sku = relationship("Sku")


class StockLog(Base):
    """库存流水"""
    __tablename__ = "stock_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # 正=入库 负=出库
    balance_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)  # produce_in / ship_out / purchase_in / etc
    biz_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    warehouse = relationship("Warehouse")
    sku = relationship("Sku")


# ---------------------------------------------------------------------------
# 库位化 / 批次化仓储能力（自 lightmes 2.5 移植）
#
# cenkormes 是单用户版：不跑多租户，但保留了 tenants 表（id=1），且
# User.tenant_id 是固定返回 1 的 property。所以这六张表沿用 lightmes 的
# tenant_id 列与表名 —— 两个好处：产品线将来能同步同一份代码；拓展包
# （stock_check / warehouse_insight / stock_transfer）不必为「有没有
# tenant_id」写两套分支。
#
# 为什么不带 StockCheck / StockCheckItem：
# cenkormes 已有 stocktakes / stocktake_items（迁移 0016），盘点主流程归它管；
# 拓展 stock_check 在此之上做批次口径增强，不需要第二套盘点单。
# ---------------------------------------------------------------------------


class WarehouseZone(Base):
    """库区（存储/收货/拣货/待检/不良/发货）"""
    __tablename__ = "warehouse_zone"
    __table_args__ = (
        UniqueConstraint("tenant_id", "warehouse_id", "code", name="uq_warehouse_zone_tenant_wh_code"),
        Index("ix_warehouse_zone_wh_type", "warehouse_id", "zone_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="storage")
    capacity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse")


class WarehouseLocation(Base):
    """库位（库区 zone / 货架 rack / 货位 bin）"""
    __tablename__ = "warehouse_location"
    __table_args__ = (
        UniqueConstraint("tenant_id", "warehouse_id", "code", name="uq_warehouse_locations_tenant_wh_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouse_zone.id", ondelete="SET NULL"), nullable=True
    )
    location_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="bin")
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouse_location.id", ondelete="SET NULL"), nullable=True, index=True
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class StockBatch(Base):
    """批次库存（一仓一库位一型号一批次一行，FIFO 按效期出库）

    同一批次可以因为调拨拆到多个库位（每库位一行），所以唯一键含 location_id。
    location_id 必须非空：MySQL 唯一索引里 NULL 互不相等，一旦某行 location_id
    为 NULL，这条唯一键对它完全失效，并发入库会产生重复批次行、库存被重复计。
    业务上从来不需要「无库位批次」—— fifo.receive() 在未指定库位时会自动落到
    ensure_default_location() 返回的默认库位。
    """
    __tablename__ = "stock_batch"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "warehouse_id", "location_id", "sku_id", "batch_no",
            name="uq_stock_batch_tenant_wh_loc_sku_batch_no",
        ),
        Index("ix_stock_batch_fifo", "tenant_id", "warehouse_id", "sku_id", "status", "expiry_date"),
        Index("ix_stock_batch_expiry", "tenant_id", "expiry_date"),
        CheckConstraint("qty_on_hand >= 0", name="ck_stock_batch_qty_on_hand_nonneg"),
        CheckConstraint("qty_reserved >= 0", name="ck_stock_batch_qty_reserved_nonneg"),
        CheckConstraint("qty_reserved <= qty_on_hand", name="ck_stock_batch_reserved_le_on_hand"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    # NOT NULL + RESTRICT：库位被批次引用时不允许删库位（只能停用），
    # 否则 SET NULL 会把批次变成无库位孤儿，连带废掉上面的唯一键。
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouse_location.id", ondelete="RESTRICT"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfg_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="qualified")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_alerted_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    expiry_alerted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse")
    location = relationship("WarehouseLocation")
    sku = relationship("Sku")


class StockLedger(Base):
    """库存流水（批次台账，正=入 负=出）"""
    __tablename__ = "stock_ledger"
    __table_args__ = (
        Index("ix_stock_ledger_tenant_batch_occurred", "tenant_id", "batch_id", "occurred_at"),
        Index("ix_stock_ledger_tenant_ref", "tenant_id", "ref_type", "ref_id"),
        Index("ix_stock_ledger_tenant_sku_occurred", "tenant_id", "sku_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_batch.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouse_location.id", ondelete="SET NULL"), nullable=True
    )
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False)
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    operator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StockTransfer(Base):
    """调拨单（仓间 / 库位间）"""
    __tablename__ = "stock_transfer"
    __table_args__ = (
        UniqueConstraint("tenant_id", "transfer_no", name="uq_stock_transfer_tenant_no"),
        Index("ix_stock_transfer_tenant_status_created", "tenant_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_no: Mapped[str] = mapped_column(String(32), nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    from_location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouse_location.id", ondelete="SET NULL"), nullable=True
    )
    to_warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    to_location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouse_location.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    from_warehouse = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    from_location = relationship("WarehouseLocation", foreign_keys=[from_location_id])
    to_location = relationship("WarehouseLocation", foreign_keys=[to_location_id])
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    items = relationship(
        "StockTransferItem",
        back_populates="transfer",
        cascade="all, delete-orphan",
        order_by="StockTransferItem.id",
    )


class StockTransferItem(Base):
    """调拨单明细"""
    __tablename__ = "stock_transfer_item"
    __table_args__ = (Index("ix_stock_transfer_item_transfer_id", "transfer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stock_transfer.id", ondelete="CASCADE"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    from_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    transfer = relationship("StockTransfer", back_populates="items")
    sku = relationship("Sku")
