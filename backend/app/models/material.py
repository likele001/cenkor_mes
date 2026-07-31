from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("code", name="uq_suppliers_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    materials = relationship("Material", back_populates="supplier")


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("code", name="uq_materials_code"),
        UniqueConstraint("sku_id", name="uq_materials_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier", back_populates="materials")
    sku = relationship("Sku")


BOM_SCOPE_SKU = "sku"
BOM_SCOPE_PRODUCT = "product"
BOM_SCOPE_GLOBAL = "global"


class MaterialBom(Base):
    """
    BOM 作用域（与 thinkmes bom_type 对应）：
    - sku：某型号专属（优先级最高）
    - product：某产品下所有型号共用（未单独配 BOM 的型号继承）
    - global：全厂默认模板（is_default=1，仅一条生效）
    """

    __tablename__ = "material_boms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default=BOM_SCOPE_SKU, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    product = relationship("Product")
    sku = relationship("Sku")
    items = relationship("MaterialBomItem", back_populates="bom", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class MaterialBomItem(Base):
    __tablename__ = "material_bom_items"
    __table_args__ = (UniqueConstraint("bom_id", "material_id", name="uq_material_bom_items_bom_material"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_boms.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty_per: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    bom = relationship("MaterialBom", back_populates="items")
    material = relationship("Material")
