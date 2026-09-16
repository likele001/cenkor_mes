# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""ERP 固定资产：台账 / 折旧 / 盘点"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FixedAsset(Base):
    """固定资产台账"""
    __tablename__ = "fixed_assets"
    __table_args__ = (UniqueConstraint("tenant_id", "asset_no", name="uq_fixed_assets_tenant_asset_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_no: Mapped[str] = mapped_column(String(32), nullable=False)  # FA...
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 设备/房屋/运输/办公/其他
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True, index=True)
    workshop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)

    original_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    residual_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    depreciation_method: Mapped[str] = mapped_column(String(16), nullable=False, server_default="straight_line")  # straight_line/double_declining/sum_of_years
    monthly_depreciation: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_use_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active", index=True)  # active/retired/scrapped
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    book_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")

    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())



class DepreciationRecord(Base):
    """折旧记录"""
    __tablename__ = "asset_depreciation_records"
    __table_args__ = (UniqueConstraint("tenant_id", "asset_id", "period", name="uq_asset_depr_tenant_asset_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    book_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class AssetCheck(Base):
    """盘点单"""
    __tablename__ = "asset_checks"
    __table_args__ = (UniqueConstraint("tenant_id", "check_no", name="uq_asset_checks_tenant_check_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    check_no: Mapped[str] = mapped_column(String(32), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)  # draft/in_progress/done
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("AssetCheckItem", back_populates="check", cascade="all, delete-orphan")


class AssetCheckItem(Base):
    """盘点明细（盘盈/盘亏）"""
    __tablename__ = "asset_check_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("asset_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    checked_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    diff_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # checked-expected
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="normal", index=True)  # normal/loss/surplus
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    check = relationship("AssetCheck", back_populates="items")
