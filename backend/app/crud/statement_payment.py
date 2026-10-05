# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""对账单核销与账龄（AR/AP 通用）——收付款的唯一出口。

口径（AR/AP 共用一套，别的模块只读不写）：
- StatementPayment：逐笔收付流水，是「收到多少钱 / 付出去多少钱」的唯一事实来源；
  statement.paid_amount 与 status 由它累计派生。
- FinanceLedger：台账流水，分两类互不混用——
  计提 ar/ap（对账确认时记，进利润表）、现金 receipt/payment（核销时记，不进利润表）。
  确认应收写一笔 ar、确认应付写一笔 ap；真金白银进出才写 receipt/payment。
  冲销不改历史行，追加一笔等额负数现金流水，账留得住。
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.approval_record import record_status
from app.crud.finance_ledger import create_ledger
from app.models.finance import Statement
from app.models.supplier_statement import SupplierStatement
from app.models.statement_payment import StatementPayment

# statement_type -> (Model, party_type, party_id 属性名)
_TYPE_MAP = {
    "statement": (Statement, "customer", "customer_id"),
    "supplier_statement": (SupplierStatement, "supplier", "supplier_id"),
}

# statement_type -> (direction, 计提科目, 现金科目)
_LEDGER_MAP = {
    "statement": ("in", "ar", "receipt"),
    "supplier_statement": ("out", "ap", "payment"),
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


def balance_of(stmt) -> Decimal:
    return Decimal(str(stmt.total_amount)) - Decimal(str(stmt.paid_amount or 0))


def create_accrual_ledger(
    db: Session,
    *,
    statement_type: str,
    stmt,
    biz_date: date,
    created_by: int | None,
    remark: str,
) -> None:
    """确认对账单＝计提：应收/应付各记一笔，与后面实际收付无关。"""
    _, party_type, party_attr = _model_for(statement_type)
    direction, accrual_category, _ = _LEDGER_MAP[statement_type]
    create_ledger(
        db,
        direction=direction,
        category=accrual_category,
        party_type=party_type,
        party_id=getattr(stmt, party_attr),
        statement_type=statement_type,
        statement_id=stmt.id,
        amount=Decimal(str(stmt.total_amount)),
        biz_date=biz_date,
        remark=remark,
        created_by=created_by,
    )


def _write_cash_ledger(
    db: Session,
    *,
    statement_type: str,
    stmt,
    amount: Decimal,
    biz_date: date,
    created_by: int | None,
    remark: str,
) -> None:
    _, party_type, party_attr = _TYPE_MAP[statement_type]
    direction, _accrual_category, cash_category = _LEDGER_MAP[statement_type]
    create_ledger(
        db,
        direction=direction,
        category=cash_category,
        party_type=party_type,
        party_id=getattr(stmt, party_attr),
        statement_type=statement_type,
        statement_id=stmt.id,
        amount=amount,
        biz_date=biz_date,
        remark=remark,
        created_by=created_by,
    )


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
    settle_date = paid_date or date.today()
    from_status = stmt.status
    p = StatementPayment(
        statement_type=statement_type,
        statement_id=statement_id,
        party_type=party_type,
        party_id=getattr(stmt, party_attr),
        amount=amt,
        paid_date=settle_date,
        method=method,
        remark=remark,
        created_by=created_by,
    )
    db.add(p)
    stmt.paid_amount = paid + amt
    stmt.status = "paid" if stmt.paid_amount >= total else "partial"
    db.flush()
    _write_cash_ledger(
        db,
        statement_type=statement_type,
        stmt=stmt,
        amount=amt,
        biz_date=settle_date,
        created_by=created_by,
        remark=remark or f"{'应收' if statement_type == 'statement' else '应付'}核销 #{stmt.code} {amt}",
    )
    record_status(
        db,
        biz_type=statement_type,
        biz_id=stmt.id,
        biz_code=stmt.code,
        action="pay",
        operator=created_by,
        from_status=from_status,
        to_status=stmt.status,
        channel="system" if created_by is None else "web",
        reason=remark,
        detail={"payment_id": p.id, "amount": str(amt), "paid_date": str(settle_date), "method": method},
    )
    return p


def settle_statement(
    db: Session,
    *,
    statement_type: str,
    statement_id: int,
    paid_date: date | None = None,
    method: str | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> StatementPayment | None:
    """整单结清（「标记已收/已付」走这里）：把未结余额一次核销掉。

    核销记录、paid_amount、现金流水三件套同时落地，缺一样对账单就和总账分家。
    已结清时不再补记，返回 None——重复点按钮不会把账付两遍。
    """
    Model, _, _ = _model_for(statement_type)
    stmt = db.get(Model, statement_id)
    if not stmt:
        raise ValueError("对账单不存在")
    if stmt.status == "draft":
        raise ValueError("需先确认对账单后才能核销")
    if stmt.status == "paid":
        return None
    balance = balance_of(stmt)
    if balance <= 0:
        from_status = stmt.status
        stmt.status = "paid"
        record_status(
            db,
            biz_type=statement_type,
            biz_id=stmt.id,
            biz_code=stmt.code,
            action="pay",
            operator=created_by,
            from_status=from_status,
            to_status=stmt.status,
            channel="system" if created_by is None else "web",
            reason=remark or "余额已为零，仅结单",
        )
        db.flush()
        return None
    return create_payment(
        db,
        statement_type=statement_type,
        statement_id=statement_id,
        amount=balance,
        paid_date=paid_date,
        method=method,
        remark=remark,
        created_by=created_by,
    )


def list_payments(db: Session, statement_type: str, statement_id: int) -> list[StatementPayment]:
    return list(db.scalars(
        select(StatementPayment)
        .where(
            StatementPayment.statement_type == statement_type,
            StatementPayment.statement_id == statement_id,
        )
        .order_by(StatementPayment.id.desc())
    ).all())


def reverse_payment(db: Session, payment_id: int, *, created_by: int | None = None) -> None:
    """冲销一笔核销：回退 paid_amount，并在总账追加一笔等额负数现金流水。

    历史流水不删——删掉就没人知道这笔钱曾经被记过一次。
    """
    p = db.get(StatementPayment, payment_id)
    if not p:
        raise ValueError("核销记录不存在")
    stmt = get_statement(db, p.statement_type, p.statement_id)
    if stmt is None:
        raise ValueError("关联对账单不存在")
    total = Decimal(str(stmt.total_amount))
    from_status = stmt.status
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
    _write_cash_ledger(
        db,
        statement_type=p.statement_type,
        stmt=stmt,
        amount=-Decimal(str(p.amount)),
        biz_date=p.paid_date or date.today(),
        created_by=created_by,
        remark=f"冲销核销#{p.id}（{stmt.code}）",
    )
    record_status(
        db,
        biz_type=p.statement_type,
        biz_id=stmt.id,
        biz_code=stmt.code,
        action="reverse",
        operator=created_by,
        from_status=from_status,
        to_status=stmt.status,
        channel="system" if created_by is None else "web",
        reason=f"冲销核销记录 #{p.id}",
        detail={"payment_id": p.id, "amount": str(-Decimal(str(p.amount)))},
    )
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
