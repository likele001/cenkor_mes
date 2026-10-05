# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""通用审批/状态变更留痕。

订单、采购单、入库单、对账单、工资条这些单据以前只把最后一次审核结果写在
confirmed_by/confirmed_at 之类的列上：改一次覆盖一次，驳回过几次、谁驳回的、
理由是什么，全都没有留下痕迹；审批流（ApprovalFlow）也只有模板没有实例。
这张表按 (biz_type, biz_id) 追加记录每次状态翻转，只写不改不删——
UPDATE/DELETE 在 ORM 层直接报错，保证它是流水而不是状态。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ApprovalRecord(Base):
    __tablename__ = "approval_records"
    __table_args__ = (
        Index("ix_approval_records_biz", "biz_type", "biz_id", "id"),
        Index("ix_approval_records_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="order/purchase_order/warehouse_entry/statement/...")
    biz_id: Mapped[int] = mapped_column(Integer, nullable=False)
    biz_code: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="单据编号快照，单据删了也认得出是谁")

    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="submit/approve/reject/confirm/cancel/pay/unpay/sign/reset")
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    operator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="姓名快照，不随用户改名/删除而丢失")
    channel: Mapped[str] = mapped_column(String(16), nullable=False, server_default="web", comment="web/h5/feishu/system")

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True, comment="附加信息，JSON 字符串")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    operator = relationship("User", foreign_keys=[operator_id])


@event.listens_for(ApprovalRecord, "before_update", propagate=True)
def _block_update(mapper, connection, target):
    raise RuntimeError("审批留痕只追加，不允许修改")


@event.listens_for(ApprovalRecord, "before_delete", propagate=True)
def _block_delete(mapper, connection, target):
    raise RuntimeError("审批留痕只追加，不允许删除")
