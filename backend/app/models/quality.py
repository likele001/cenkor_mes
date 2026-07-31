"""质量检测体系：质检模板、缺陷代码、检测记录"""

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class InspectionTemplate(Base):
    """质检模板（如"焊接工序检查项"）"""
    __tablename__ = "inspection_templates"
    __table_args__ = (UniqueConstraint("code", name="uq_inspection_templates_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    # 关联工序（可选）: 此模板适用于哪个工序
    process_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("InspectionTemplateItem", back_populates="template", cascade="all, delete-orphan",
                         order_by="InspectionTemplateItem.seq")


class InspectionTemplateItem(Base):
    """质检模板明细项"""
    __tablename__ = "inspection_template_items"
    __table_args__ = (UniqueConstraint("template_id", "seq", name="uq_inspection_template_items_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # pass_fail — 合格/不合格  |  measure — 测量值  |  text — 文本描述
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pass_fail")

    # 测量类型专用
    standard_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upper_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lower_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    template = relationship("InspectionTemplate", back_populates="items")


class DefectCode(Base):
    """缺陷代码"""
    __tablename__ = "defect_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_defect_codes_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # critical — 致命  |  major — 主要  |  minor — 次要
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="minor")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class InspectionRecord(Base):
    """检测记录 — 每次 QC 审核时逐项填写"""
    __tablename__ = "inspection_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联到审核流水
    report_unit_audit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("report_unit_audits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_template_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # pass — 合格  |  fail — 不合格  |  na — 不适用
    result: Mapped[str] = mapped_column(String(8), nullable=False, server_default="pass")

    # 测量值（item_type=measure 时使用）
    measured_value: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 不合格时关联的缺陷代码
    defect_code_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("defect_codes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    audit = relationship("ReportUnitAudit", foreign_keys=[report_unit_audit_id])
    template_item = relationship("InspectionTemplateItem")
    defect_code = relationship("DefectCode")
