from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

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

    slip.signature_attachment_id = attachment_id
    slip.signed_at = datetime.now()
    slip.confirm_status = "signed"
    slip.reject_reason = None
    slip.rejected_at = None
    db.flush()
    return slip


def reject_salary_slip(
    db: Session,
    user_id: int,
    month: str | None,
    reason: str,
) -> SalarySlip:
    month = _month_default(month)
    slip = ensure_salary_slip(db, user_id=user_id, month=month)
    if slip.signed_at:
        raise ValueError("工资条已签名，不能拒签")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("拒签原因不能为空")

    slip.confirm_status = "rejected"
    slip.reject_reason = reason[:255]
    slip.rejected_at = datetime.now()
    slip.signature_attachment_id = None
    slip.signed_at = None
    db.flush()
    return slip


def reset_salary_slip_confirm(db: Session, slip_id: int) -> SalarySlip:
    slip = db.scalar(select(SalarySlip).where(SalarySlip.id == slip_id))
    if not slip:
        raise ValueError("工资条不存在")
    slip.confirm_status = "pending"
    slip.reject_reason = None
    slip.rejected_at = None
    slip.signature_attachment_id = None
    slip.signed_at = None
    db.flush()
    return slip


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
