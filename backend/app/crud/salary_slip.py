# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""工资条：金额汇总、员工签收、以及「厂里到底付了没有」的发放落账。

confirm_status（员工签收）与 pay_status（已发放）是两条独立状态线：
签收只说明员工认这笔数，发放才说明钱真的出去了——后者必须留一行总账现金流水，
否则人力成本永远不进现金台账，老板看到的支出口径就缺一块。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.crud.approval_record import record_status
from app.crud.finance_ledger import create_ledger
from app.models.attachment import Attachment
from app.models.salary import SalaryItem
from app.models.salary_allowance import SalaryAllowance
from app.models.salary_slip import SalarySlip
from app.models.user import User


def _month_default(month: str | None) -> str:
    return month or datetime.now().strftime("%Y-%m")


def calc_salary_slip_amounts(db: Session, user_id: int, month: str) -> dict:
    piece_row = db.execute(
        select(
            func.coalesce(func.sum(SalaryItem.amount), 0).label("item_amount"),
            func.coalesce(func.sum(SalaryItem.good_qty), 0).label("total_qty"),
        ).where(
            SalaryItem.user_id == user_id,
            SalaryItem.month == month,
            SalaryItem.item_type == "piece",
        )
    ).one()

    hourly_row = db.execute(
        select(
            func.coalesce(func.sum(SalaryItem.amount), 0).label("hourly_amount"),
            func.coalesce(func.sum(SalaryItem.work_hours), 0).label("hourly_hours"),
        ).where(
            SalaryItem.user_id == user_id,
            SalaryItem.month == month,
            SalaryItem.item_type == "hourly",
        )
    ).one()

    allowance_row = db.execute(
        select(
            func.coalesce(func.sum(case((SalaryAllowance.allowance_type == "bonus", SalaryAllowance.amount), else_=0)), 0).label(
                "bonus_amount"
            ),
            func.coalesce(
                func.sum(case((SalaryAllowance.allowance_type == "deduction", SalaryAllowance.amount), else_=0)), 0
            ).label("deduction_amount"),
        ).where(
            SalaryAllowance.user_id == user_id,
            SalaryAllowance.month == month,
        )
    ).one()

    item_amount = Decimal(str(piece_row.item_amount))
    hourly_amount = Decimal(str(hourly_row.hourly_amount))
    hourly_hours = Decimal(str(hourly_row.hourly_hours))
    bonus_amount = Decimal(str(allowance_row.bonus_amount))
    deduction_amount = Decimal(str(allowance_row.deduction_amount))
    net_amount = item_amount + hourly_amount + bonus_amount - deduction_amount
    total_qty = int(piece_row.total_qty or 0)

    return {
        "item_amount": item_amount,
        "hourly_amount": hourly_amount,
        "hourly_hours": hourly_hours,
        "bonus_amount": bonus_amount,
        "deduction_amount": deduction_amount,
        "net_amount": net_amount,
        "total_qty": total_qty,
    }


def ensure_salary_slip(db: Session, user_id: int, month: str | None) -> SalarySlip:
    month = _month_default(month)
    slip = db.scalar(
        select(SalarySlip).where(SalarySlip.user_id == user_id, SalarySlip.month == month)
    )
    amounts = calc_salary_slip_amounts(db, user_id=user_id, month=month)
    if not slip:
        slip = SalarySlip(user_id=user_id, month=month, **amounts)
        db.add(slip)
        db.flush()
        return slip

    slip.item_amount = amounts["item_amount"]
    slip.hourly_amount = amounts["hourly_amount"]
    slip.hourly_hours = amounts["hourly_hours"]
    slip.bonus_amount = amounts["bonus_amount"]
    slip.deduction_amount = amounts["deduction_amount"]
    slip.net_amount = amounts["net_amount"]
    slip.total_qty = amounts["total_qty"]
    db.flush()
    return slip


def sign_salary_slip(
    db: Session,
    user_id: int,
    month: str | None,
    attachment_id: int,
    *,
    channel: str = "h5",
) -> SalarySlip:
    month = _month_default(month)
    slip = ensure_salary_slip(db, user_id=user_id, month=month)
    if slip.signed_at:
        raise ValueError("工资条已签名")
    if slip.confirm_status == "rejected":
        raise ValueError("工资条已拒签，请联系管理员处理后再签名")

    att = db.get(Attachment, attachment_id)
    if not att:
        raise ValueError("签名附件不存在")

    from_status = slip.confirm_status
    slip.signature_attachment_id = attachment_id
    slip.signed_at = datetime.now()
    slip.confirm_status = "signed"
    slip.reject_reason = None
    slip.rejected_at = None
    record_status(
        db,
        biz_type="salary_slip",
        biz_id=slip.id,
        biz_code=slip.month,
        action="sign",
        operator=user_id,
        from_status=from_status,
        to_status=slip.confirm_status,
        channel=channel,
        created_at=slip.signed_at,
        detail={"net_amount": str(slip.net_amount), "attachment_id": attachment_id},
    )
    db.flush()
    return slip


def reject_salary_slip(
    db: Session,
    user_id: int,
    month: str | None,
    reason: str,
    *,
    channel: str = "h5",
) -> SalarySlip:
    month = _month_default(month)
    slip = ensure_salary_slip(db, user_id=user_id, month=month)
    if slip.signed_at:
        raise ValueError("工资条已签名，不能拒签")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("拒签原因不能为空")

    from_status = slip.confirm_status
    slip.confirm_status = "rejected"
    slip.reject_reason = reason[:255]
    slip.rejected_at = datetime.now()
    slip.signature_attachment_id = None
    slip.signed_at = None
    record_status(
        db,
        biz_type="salary_slip",
        biz_id=slip.id,
        biz_code=slip.month,
        action="reject",
        operator=user_id,
        from_status=from_status,
        to_status=slip.confirm_status,
        reason=slip.reject_reason,
        channel=channel,
        created_at=slip.rejected_at,
        detail={"net_amount": str(slip.net_amount)},
    )
    db.flush()
    return slip


def reset_salary_slip_confirm(
    db: Session,
    slip_id: int,
    *,
    operator: User | int | None = None,
    reason: str | None = None,
) -> SalarySlip:
    slip = db.scalar(select(SalarySlip).where(SalarySlip.id == slip_id))
    if not slip:
        raise ValueError("工资条不存在")
    from_status = slip.confirm_status
    slip.confirm_status = "pending"
    slip.reject_reason = None
    slip.rejected_at = None
    slip.signature_attachment_id = None
    slip.signed_at = None
    record_status(
        db,
        biz_type="salary_slip",
        biz_id=slip.id,
        biz_code=slip.month,
        action="reset",
        operator=operator,
        from_status=from_status,
        to_status=slip.confirm_status,
        reason=reason,
        detail={"net_amount": str(slip.net_amount)},
    )
    db.flush()
    return slip


# ── 发放（真金白银那一段）──


def pay_slip(
    db: Session,
    slip: SalarySlip,
    *,
    operator_id: int | None,
    paid_at: datetime | None = None,
    remark: str | None = None,
) -> SalarySlip:
    """记一笔工资发放：状态、发放人、总账现金流水同时落地。"""
    if slip.pay_status == "paid":
        raise ValueError(f"{slip.month} 工资条已发放，不要重复记账")
    if slip.confirm_status == "rejected":
        raise ValueError(f"{slip.month} 工资条被员工拒签，先处理异议再发放")
    net = Decimal(str(slip.net_amount or 0))
    if net <= 0:
        raise ValueError(f"{slip.month} 实发金额为 0，无需发放")

    paid_at = paid_at or datetime.now()
    slip.pay_status = "paid"
    slip.paid_at = paid_at
    slip.paid_by = operator_id
    slip.paid_remark = (remark or "")[:255] or None
    record_status(
        db,
        biz_type="salary_slip",
        biz_id=slip.id,
        biz_code=slip.month,
        action="pay",
        operator=operator_id,
        from_status="unpaid",
        to_status=slip.pay_status,
        reason=remark,
        created_at=paid_at,
        detail={"net_amount": str(net)},
    )
    db.flush()
    create_ledger(
        db,
        direction="out",
        category="labor",
        party_type="employee",
        party_id=slip.user_id,
        statement_type="salary_slip",
        statement_id=slip.id,
        amount=net,
        biz_date=paid_at.date(),
        remark=f"发放{slip.month}工资 #{slip.id}",
        created_by=operator_id,
    )
    return slip


def pay_month(
    db: Session,
    *,
    month: str,
    operator_id: int | None,
    user_ids: list[int] | None = None,
    paid_at: datetime | None = None,
    remark: str | None = None,
) -> list[SalarySlip]:
    """按月批量发放：已发放的跳过，实发为 0 的跳过——批量按钮不该因为一张旧单报错。"""
    stmt = select(SalarySlip).where(SalarySlip.month == month, SalarySlip.pay_status != "paid")
    if user_ids:
        stmt = stmt.where(SalarySlip.user_id.in_(user_ids))
    slips = list(db.scalars(stmt.order_by(SalarySlip.user_id)).all())
    paid: list[SalarySlip] = []
    for slip in slips:
        if Decimal(str(slip.net_amount or 0)) <= 0 or slip.confirm_status == "rejected":
            continue
        paid.append(pay_slip(db, slip, operator_id=operator_id, paid_at=paid_at, remark=remark))
    return paid


def unpay_slip(db: Session, slip: SalarySlip, *, operator_id: int | None, reason: str | None = None) -> SalarySlip:
    """撤销发放：现金流水追加等额负数行，历史流水保持原样。"""
    if slip.pay_status != "paid":
        raise ValueError(f"{slip.month} 工资条尚未发放")
    net = Decimal(str(slip.net_amount or 0))
    slip.pay_status = "unpaid"
    slip.paid_at = None
    slip.paid_by = None
    slip.paid_remark = (reason or "")[:255] or None
    record_status(
        db,
        biz_type="salary_slip",
        biz_id=slip.id,
        biz_code=slip.month,
        action="unpay",
        operator=operator_id,
        from_status="paid",
        to_status=slip.pay_status,
        reason=reason,
        detail={"net_amount": str(-net)},
    )
    db.flush()
    create_ledger(
        db,
        direction="out",
        category="labor",
        party_type="employee",
        party_id=slip.user_id,
        statement_type="salary_slip",
        statement_id=slip.id,
        amount=-net,
        biz_date=date.today(),
        remark=f"撤销发放{slip.month}工资 #{slip.id}",
        created_by=operator_id,
    )
    return slip


def month_payable_summary(db: Session, month: str) -> dict:
    """本月待发/已发合计，给发放按钮当确认文案。"""
    rows = db.execute(
        select(
            SalarySlip.pay_status,
            func.coalesce(func.sum(SalarySlip.net_amount), 0).label("amount"),
            func.count(SalarySlip.id).label("cnt"),
        )
        .where(SalarySlip.month == month)
        .group_by(SalarySlip.pay_status)
    ).all()
    paid_amount = Decimal("0")
    unpaid_amount = Decimal("0")
    paid_count = 0
    unpaid_count = 0
    for status, amount, cnt in rows:
        if status == "paid":
            paid_amount += Decimal(str(amount))
            paid_count += int(cnt)
        else:
            unpaid_amount += Decimal(str(amount))
            unpaid_count += int(cnt)
    return {
        "month": month,
        "paid_amount": float(paid_amount),
        "unpaid_amount": float(unpaid_amount),
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
    }


def list_salary_slips(
    db: Session,
    month: str | None = None,
    user_id: int | None = None,
    signed: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[tuple[SalarySlip, User]]:
    stmt = select(SalarySlip, User).join(User, User.id == SalarySlip.user_id)
    if month:
        stmt = stmt.where(SalarySlip.month == month)
    if user_id is not None:
        stmt = stmt.where(SalarySlip.user_id == user_id)
    if signed is True:
        stmt = stmt.where(SalarySlip.signed_at.is_not(None))
    if signed is False:
        stmt = stmt.where(SalarySlip.signed_at.is_(None))
    stmt = stmt.order_by(SalarySlip.month.desc(), SalarySlip.user_id).offset(offset).limit(limit)
    return list(db.execute(stmt).all())
