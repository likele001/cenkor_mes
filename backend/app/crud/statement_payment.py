# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""对账单核销与账龄（AR/AP 通用）。

核销独立于 FinanceLedger 总账：仅累计回写 statement.paid_amount 与状态，
不影响利润/GL 口径。statement_type 多态区分应收/应付。
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Statement
from app.models.supplier_statement import SupplierStatement
from app.models.statement_payment import StatementPayment

# statement_type -> (Model, party_type, party_id 属性名)
_TYPE_MAP = {
    "statement": (Statement, "customer", "customer_id"),
    "supplier_statement": (SupplierStatement, "supplier", "supplier_id"),
}

BUCKET_ORDER = ["not_due", "1_30", "31_60", "61_90", "90_plus"]


def _model_for(statement_type: str):
    entry = _TYPE_MAP.get(statement_type)
    if not entry:
        raise ValueError("对账单类型非法")
    return entry


def get_statement(db: Session, statement_type: str, statement_id: int):
    Model, _, _ = _model_for(statement_type)
    return db.get(Model, statement_id)


def create_payment(
    db: Session,
    *,
    statement_type: str,
    statement_id: int,
    amount: Decimal,
    paid_date: date | None = None,
    method: str | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> StatementPayment:
    Model, party_type, party_attr = _model_for(statement_type)
    stmt = db.get(Model, statement_id)
    if not stmt:
        raise ValueError("对账单不存在")
    if stmt.status == "draft":
        raise ValueError("需先确认对账单后才能核销")
    if stmt.status == "paid":
        raise ValueError("对账单已结清")
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("核销金额需大于0")
    total = Decimal(str(stmt.total_amount))
    paid = Decimal(str(stmt.paid_amount or 0))
    balance = total - paid
    if amt > balance:
        raise ValueError(f"核销金额超过未结余额（{balance}）")
    p = StatementPayment(
        statement_type=statement_type,
        statement_id=statement_id,
        party_type=party_type,
        party_id=getattr(stmt, party_attr),
        amount=amt,
        paid_date=paid_date or date.today(),
        method=method,
        remark=remark,
        created_by=created_by,
    )
    db.add(p)
    stmt.paid_amount = paid + amt
    stmt.status = "paid" if stmt.paid_amount >= total else "partial"
    db.flush()
    return p


def list_payments(db: Session, statement_type: str, statement_id: int) -> list[StatementPayment]:
    return list(db.scalars(
        select(StatementPayment)
        .where(
            StatementPayment.statement_type == statement_type,
            StatementPayment.statement_id == statement_id,
        )
        .order_by(StatementPayment.id.desc())
    ).all())


def reverse_payment(db: Session, payment_id: int) -> None:
    p = db.get(StatementPayment, payment_id)
    if not p:
        raise ValueError("核销记录不存在")
    stmt = get_statement(db, p.statement_type, p.statement_id)
    if stmt is None:
        raise ValueError("关联对账单不存在")
    total = Decimal(str(stmt.total_amount))
    paid = Decimal(str(stmt.paid_amount or 0)) - Decimal(str(p.amount))
    if paid < 0:
        paid = Decimal("0")
    stmt.paid_amount = paid
    if paid <= 0:
        stmt.status = "confirmed"
    elif paid < total:
        stmt.status = "partial"
    else:
        stmt.status = "paid"
    db.delete(p)
    db.flush()


def _bucket(days_overdue: int) -> str:
    if days_overdue < 0:
        return "not_due"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "90_plus"


def get_aging(db: Session, direction: str) -> dict:
    """账龄：对未结对账单(confirmed/partial)按到期日分档聚合。direction: ar|ap。"""
    Model = SupplierStatement if direction == "ap" else Statement
    today = date.today()
    rows = db.scalars(select(Model).where(Model.status.in_(("confirmed", "partial")))).all()
    items: list[dict] = []
    agg = {b: {"count": 0, "balance": Decimal("0")} for b in BUCKET_ORDER}
    total_balance = Decimal("0")
    for s in rows:
        bal = Decimal(str(s.total_amount)) - Decimal(str(s.paid_amount or 0))
        if bal <= 0:
            continue
        anchor = s.due_date or s.period_end or (s.created_at.date() if s.created_at else today)
        days = (today - anchor).days
        b = _bucket(days)
        agg[b]["count"] += 1
        agg[b]["balance"] += bal
        total_balance += bal
        items.append({
            "statement_id": s.id,
            "code": s.code,
            "amount": float(Decimal(str(s.total_amount))),
            "paid_amount": float(Decimal(str(s.paid_amount or 0))),
            "balance": float(bal),
            "due_date": str(anchor),
            "days_overdue": days,
            "bucket": b,
            "status": s.status,
        })
    items.sort(key=lambda x: x["days_overdue"], reverse=True)
    buckets = [{"bucket": b, "count": agg[b]["count"], "balance": float(agg[b]["balance"])} for b in BUCKET_ORDER]
    overdue = sum((agg[b]["balance"] for b in BUCKET_ORDER if b != "not_due"), Decimal("0"))
    return {
        "direction": direction,
        "as_of": str(today),
        "total_balance": float(total_balance),
        "overdue_balance": float(overdue),
        "buckets": buckets,
        "items": items,
    }
