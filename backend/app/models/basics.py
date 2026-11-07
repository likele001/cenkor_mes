# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""宿主核心基础台账（第二批）

上一轮补的是质量主线（检验单 + 检验台账 + 不良品处置），这一轮补五张「现场天天在用、
系统里却没有」的基础台账。它们共同的口径，先钉死再写代码：

1. **只登记，不越界改别人的单据**。返工单不改 `reports.good_qty`（报工是审过的历史，
   改了工资和良率都会跟着变）；物料替代不自动改 BOM 行；ECN 不自动重写 BOM；
   停机记录不改设备状态；供应商评分不改供应商主档。这些都只出「决定 + 事实」。
2. **可重复执行要幂等**。一条 `return_process` 处置明细只能生成一张返工单，靠唯一键 +
   生成前查重双重保证，批准接口被重复点也不会冒出两张派工。
3. **软引用优先**。`inspection_orders.report_id` / `process_id`、ECN 的 sku/product/bom
   这类字段用普通 Integer + index，不建外键：历史单据要能独立留存，不能因为主档被删就
   连质量证据一起消失。需要名称时查表补，查不到就显示 ID，不报错。

评分口径（唯一实现在 `app/crud/basics.py` 的 `SCORE_WEIGHTS`）：
    total = 质量×0.40 + 交期×0.30 + 价格×0.20 + 服务×0.10（各分项 0~100）
    A ≥ 90 / B ≥ 80 / C ≥ 70 / D < 70
权重是固定口径不是配置项：改权重等于让历史评分失去可比性，要改得连同历史重算一起做。
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

REWORK_STATUSES = ("pending", "in_progress", "done", "cancelled")
ECN_TYPES = ("bom", "process", "document", "other")
ECN_STATUSES = ("draft", "pending", "approved", "rejected", "implemented", "cancelled")
DOWNTIME_REASONS = ("breakdown", "changeover", "material", "quality", "maintenance", "other")
DOWNTIME_STATUSES = ("open", "closed")
SCORE_GRADES = ("A", "B", "C", "D")


class ReworkOrder(Base):
    """返工单：把处置单里「退工序返工」从一句登记变成一张能派工、能完成的任务。

    挂在 `disposition_items` 的一行上；`disposition_item_id` 唯一，保证幂等。
    """
    __tablename__ = "rework_orders"
    __table_args__ = (
        UniqueConstraint("code", name="uq_rework_orders_code"),
        UniqueConstraint("disposition_item_id", name="uq_rework_orders_item"),
        CheckConstraint(
            "status IN ('pending','in_progress','done','cancelled')",
            name="ck_rework_orders_status",
        ),
        CheckConstraint("qty > 0", name="ck_rework_orders_qty_positive"),
        CheckConstraint(
            "done_qty IS NULL OR (done_qty >= 0 AND done_qty <= qty)",
            name="ck_rework_orders_done_qty",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending", index=True)

    disposition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispositions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disposition_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("disposition_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    work_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 退回到哪道工序返工，来自处置明细的 target_process_id
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    done_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    assigned_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MaterialSubstitute(Base):
    """物料替代关系：缺料时系统能给出「可换谁、换多少、哪个优先」，而不是停线等人拍脑袋。

    只登记关系，不改 `material_bom_items`。真正领料用哪一颗，由仓储发料单决定。
    """
    __tablename__ = "material_substitutes"
    __table_args__ = (
        UniqueConstraint(
            "material_id", "substitute_material_id", "bom_id",
            name="uq_material_substitutes_relation",
        ),
        CheckConstraint("material_id <> substitute_material_id", name="ck_material_substitutes_self"),
        CheckConstraint("ratio > 0", name="ck_material_substitutes_ratio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    substitute_material_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 为空表示对全部 BOM 生效；填了则只对该 BOM 生效
    bom_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("material_boms.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 替代比例：1 表示 1:1 换料，2 表示 1 个原料需 2 个替代料
    ratio: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False, server_default="1")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EngineeringChange(Base):
    """工程变更 ECN：BOM / 工艺 / 图纸变更的受控留痕。

    状态机：draft → pending → approved → implemented，pending 可 rejected，
    draft/pending 可 cancelled。`before_snapshot` / `after_snapshot` 存变更前后摘要（JSON 文本），
    是「当初改了什么」的证据；系统不据此自动改 BOM——执行结果由 implemented 时的
    `applied_at` 和说明登记，避免一次点击把生产主数据悄悄改掉。
    """
    __tablename__ = "engineering_changes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_engineering_changes_code"),
        CheckConstraint(
            "change_type IN ('bom','process','document','other')",
            name="ck_engineering_changes_type",
        ),
        CheckConstraint(
            "status IN ('draft','pending','approved','rejected','implemented','cancelled')",
            name="ck_engineering_changes_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="bom", index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)

    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bom_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EquipmentDowntime(Base):
    """设备停机记录：OEE 的「时间损失」这一格，宿主以前完全没有源头数据。

    口径：`duration_minutes` 一律由 `ended_at - started_at` 算（四舍五入到分钟），
    不接受前端直接传时长——手工填的时长和起止时间对不上时，后面的统计全废。
    未结束的记录 status=open、时长为空，统计只算 closed 的。
    """
    __tablename__ = "equipment_downtimes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_equipment_downtimes_code"),
        CheckConstraint(
            "reason_code IN ('breakdown','changeover','material','quality','maintenance','other')",
            name="ck_equipment_downtimes_reason",
        ),
        CheckConstraint(
            "status IN ('open','closed')", name="ck_equipment_downtimes_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reason_code: Mapped[str] = mapped_column(String(16), nullable=False, server_default="breakdown", index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open", index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SupplierScore(Base):
    """供应商评分：按期间给供应商打分，形成可比较的等级序列。

    同一供应商同一期间只允许一条（唯一键），重复录要改旧的那条而不是新增——
    否则「平均分」会被重复评分悄悄拉偏。
    """
    __tablename__ = "supplier_scores"
    __table_args__ = (
        UniqueConstraint("supplier_id", "period", name="uq_supplier_scores_period"),
        CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_supplier_scores_total"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    quality_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    delivery_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    price_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    service_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    total_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    grade: Mapped[str] = mapped_column(String(4), nullable=False, server_default="D", index=True)

    evaluated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
