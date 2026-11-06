# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""不良品处置单

报工单只记了「不良多少件」（`reports.bad_qty`），但不良品**去了哪里**从来没有记录：
返修了还是报废了、报废损失多少钱、让步接收是谁批的、退回哪道工序返工——全在车间口头
和纸质单上。质量成本分析（付费扩展 `quality_cost_analysis`）只能拿 `bad_qty` 乘单价
估个报废损失，因为系统确实不知道有几件真报废了。这张单子补的就是这一段。

一张处置单挂在**一条报工**上，可以拆多行明细，因为一批不良往往是混合处置：

    report.bad_qty = 10  →  3 报废 + 5 返修 + 2 让步接收

口径上必须钉死的三条：

1. **报工单是不可改的历史**。处置单闭环时登记的实际返修良品数 `done_qty` 只留在处置单里，
   **不回写 `reports.good_qty`**——回写等于篡改已经审核过的报工，工资和良率都会跟着变。
2. **同一批不良不能被处置两次**。同一报工下所有「有效」处置单（不含已驳回/已作废）的
   数量之和不得超过 `reports.bad_qty`，校验在 crud 层做，见 `create_disposition`。
3. **处置单不直接改库存**。不良品一般从未进过良品库，报废实物出库属于仓储业务，
   走仓储的出库单；这里只出「决定 + 损失金额」，不碰 `stocks.qty`。

状态机是单向的，`approved` 之后只能闭环不能回退：

    draft ──提交──> pending ──批准──> approved ──闭环──> closed
      │               │  └──驳回──> rejected ──提交──┘
      └──作废─────────┴──作废──> cancelled（draft/pending/rejected 可作废）
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# rework 返修 | scrap 报废 | concede 让步接收 | return_process 退工序返工
DISPOSITION_METHODS = ("rework", "scrap", "concede", "return_process")

# draft 草稿 | pending 待审批 | approved 已批准 | rejected 已驳回 | closed 已闭环 | cancelled 已作废
DISPOSITION_STATUSES = ("draft", "pending", "approved", "rejected", "closed", "cancelled")

# 这几种状态视为「没在处置」：驳回和作废不占报工的不良量额度
RELEASED_STATUSES = ("rejected", "cancelled")


class Disposition(Base):
    """不良品处置单（表头）"""
    __tablename__ = "dispositions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_dispositions_code"),
        CheckConstraint(
            "status IN ('draft','pending','approved','rejected','closed','cancelled')",
            name="ck_dispositions_status",
        ),
        CheckConstraint("total_qty > 0", name="ck_dispositions_total_qty_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)

    # 挂靠点：一条报工的不良量。task/work_order/sku/process 是为了列表和筛选冗余下来的，
    # 建单时从 report.task 一路取，之后不再跟随变动（报工本身也不允许改挂任务）。
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    work_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    process_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # 制单时该报工的不良量快照，用于展示「本批不良 10，本次处置 8，还差 2」
    bad_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 明细数量之和，由 crud 重算（列表页不必把明细全捞出来做聚合）
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 报废损失金额合计，手工填（没有可靠的成本口径就不自动算，见模块注释第 3 条）
    scrap_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")

    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    items = relationship(
        "DispositionItem",
        back_populates="disposition",
        cascade="all, delete-orphan",
        order_by="DispositionItem.id",
    )
    report = relationship("Report")
    task = relationship("Task")
    sku = relationship("Sku")
    process = relationship("Process")


class DispositionItem(Base):
    """处置明细：一行一种处置方式"""
    __tablename__ = "disposition_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_disposition_items_qty_positive"),
        CheckConstraint(
            "method IN ('rework','scrap','concede','return_process')",
            name="ck_disposition_items_method",
        ),
        CheckConstraint(
            "done_qty IS NULL OR (done_qty >= 0 AND done_qty <= qty)",
            name="ck_disposition_items_done_qty",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disposition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispositions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    method: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    defect_code_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("defect_codes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # 仅 return_process：退回到哪道工序返工
    target_process_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # 闭环时登记的实际结果：返修/退工序填回来的良品数，报废/让步接收填实际执行数量
    done_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    disposition = relationship("Disposition", back_populates="items")
    defect_code = relationship("DefectCode")
    target_process = relationship("Process", foreign_keys=[target_process_id])
