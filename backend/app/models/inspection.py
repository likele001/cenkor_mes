# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""检验单（IQC 来料 / IPQC 制程 / OQC 出货 / FAI 首件）

宿主原本只有「质检模板 + 缺陷码 + 逐件检验记录」：
- `inspection_templates` / `inspection_template_items` 定义「查什么」
- `inspection_records` 在**逐件报工审核**时记录「每一件查得怎么样」

但真正决定物料与产品能不能放行的，是**按批次的检验单**，宿主从来没有这张表：
- 采购收货直接入库，来料没有任何检验（`purchase/orders.py::receive_api`）
- 整批报工终审只改状态，不带任何检验依据
- 发货前没有出货检验

四类检验在数据结构上是同一件事，区别只在「挂在哪张来源单上」：

    iqc  来料检验 → 采购单 / 供应商 / 物料
    ipqc 制程检验 → 工单 / 工序 / 产品
    oqc  出货检验 → 发货单 / 客户
    fai  首件检验 → 任务 / 工序 / 产品（首件确认）

所以一张表 + `inspection_type` 就能覆盖，不需要四套模块。

口径上必须钉死的三条：

1. **模板项要快照到检验单上**。模板日后会被改，但三个月前那批货是按当时的判定标准检的。
   检验单明细复制 `item_name` / `standard_value` / `upper_limit` / `lower_limit` / `unit` /
   `is_required`，`template_item_id` 只作溯源线索，**判定一律按快照**。
2. **测量项自动判合格**。`item_type=measure` 且上下限都是数字时，录了 `measured_value`
   就自动算出 pass/fail，不靠人再点一次——人点的那一下最容易出错。
3. **检验单不改库存、不改来源单据状态**。IQC 判不合格，处置决定（退货 / 让步接收 / 返工 /
   报废）登记在 `handling` 上；实物退运走采购退货单、报废走仓储出库单。检验单只负责
   「判没判过、按什么判的、谁判的」，不越界去改别人的账。

状态机：

    draft ──提交──> pending ──判定──> passed ──登记关闭(closed_at)──>
                                     └──> failed ──登记关闭(closed_at)──>

「已关闭」不用独立状态，而用 `closed_at` 是否有值表示。原因是：一旦有了 `closed` 状态，
`passed → closed` 就把「当初判的是合格」这个信息抹掉了，合格率统计会直接失真。
判定结论是既成事实，关闭只是「这件事办完了」的标记，两者必须分开记。

`passed` / `failed` 之后明细不可再改：判定结果是既成事实，改了就没有追溯意义；
要重检就开新单。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# iqc 来料 | ipqc 制程 | oqc 出货 | fai 首件
INSPECTION_TYPES = ("iqc", "ipqc", "oqc", "fai")

# draft 草稿 | pending 待检验 | passed 合格 | failed 不合格 | cancelled 已作废
# 注意没有 closed：「已关闭」由 closed_at 表示，避免抹掉原判定结论
INSPECTION_STATUSES = ("draft", "pending", "passed", "failed", "cancelled")

# 判定后不可再改明细的状态
LOCKED_STATUSES = ("passed", "failed", "cancelled")

# 可作废的状态
CANCELLABLE_STATUSES = ("draft", "pending")

# 不合格后的处置决定（纯登记，不联动库存与来源单据）
# return 退货 | accept 让步接收 | rework 返工 | scrap 报废
INSPECTION_HANDLINGS = ("return", "accept", "rework", "scrap")

# 单项检验结果：pass 合格 | fail 不合格 | na 不适用 | 空串表示还没检
ITEM_RESULTS = ("pass", "fail", "na")

# 来源单据类型（report 是整批报工终审的挂靠点，见 0019）
SOURCE_TYPES = ("purchase_order", "work_order", "shipment", "task", "report", "manual")


class InspectionOrder(Base):
    """检验单（表头）"""
    __tablename__ = "inspection_orders"
    __table_args__ = (
        UniqueConstraint("code", name="uq_inspection_orders_code"),
        CheckConstraint(
            "inspection_type IN ('iqc','ipqc','oqc','fai')",
            name="ck_inspection_orders_type",
        ),
        CheckConstraint(
            "status IN ('draft','pending','passed','failed','cancelled')",
            name="ck_inspection_orders_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)

    # ── 来源单据（手工建单时 source_type=manual、source_id 为空）──
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="manual")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 冗余来源单号：来源单据日后可能被软删或不可达，单号必须留在检验单上
    source_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── 联动挂靠点（0019）──
    # 都是「软引用」：普通 Integer + 索引，不建外键。检验单是质量证据，
    # 不能因为报工或工序主档被删就一起消失；查得到名称就显示，查不到就显示 ID。
    # report_id：整批报工终审时作为检验依据（source_type=report 时 source_id 同时指向它）
    # process_id：FAI 首件 / IPQC 制程检验所在工序，用于按工序筛选与统计
    report_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # ── 检验对象 ──
    # IQC 检验物料，其余检验产品（SKU）。两者都可为空（纯手工建单时用 item_name 描述）
    material_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("skus.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # 检验对象名称快照（物料/SKU 改名后历史单据仍可读）
    item_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # ── 供应商 / 客户（IQC 记供应商，OQC 记客户，其余可空）──
    supplier_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ── 数量口径：送检 / 抽样 / 判定接收 / 判定拒收 ──
    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sample_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    accept_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reject_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # ── 检验依据 ──
    # 模板只在建单时用来展开明细；明细已快照，模板日后改动不影响本单
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("inspection_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ── 不合格处置决定（纯登记）──
    handling: Mapped[str | None] = mapped_column(String(16), nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 人 ──
    inspector_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship(
        "InspectionOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="InspectionOrderItem.seq",
    )
    inspector = relationship("User", foreign_keys=[inspector_id])
    creator = relationship("User", foreign_keys=[created_by])

    @property
    def is_locked(self) -> bool:
        return self.status in LOCKED_STATUSES

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None


class InspectionOrderItem(Base):
    """检验单明细项 —— 模板项的快照 + 本单的实测结果"""
    __tablename__ = "inspection_order_items"
    __table_args__ = (
        UniqueConstraint("inspection_order_id", "seq", name="uq_inspection_order_items_seq"),
        CheckConstraint(
            "result IN ('pass','fail','na')",
            name="ck_inspection_order_items_result",
        ),
        CheckConstraint(
            "item_type IN ('pass_fail','measure','text')",
            name="ck_inspection_order_items_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # 溯源用：模板日后改动或删除都不影响本单判定
    template_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("inspection_template_items.id", ondelete="SET NULL"), nullable=True
    )

    # ── 以下五项是建单时从模板复制来的快照 ──
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pass_fail")
    standard_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upper_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lower_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    # ── 本单实测 ──
    # pass / fail / na；NULL 表示还没检
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    measured_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    defect_code_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("defect_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    order = relationship("InspectionOrder", back_populates="items")
    defect_code = relationship("DefectCode")
