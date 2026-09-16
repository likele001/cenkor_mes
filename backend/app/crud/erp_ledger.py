# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""ERP 财务总账 CRUD"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.erp_ledger import AccountSubject, Voucher, VoucherEntry


# ---------- 科目 ----------
def list_accounts(db: Session, tenant_id: int, *, active_only: bool = False) -> list[AccountSubject]:
    stmt = select(AccountSubject).where(AccountSubject.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(AccountSubject.is_active.is_(True))
    stmt = stmt.order_by(AccountSubject.code.asc())
    return list(db.scalars(stmt).all())


def get_account(db: Session, tenant_id: int, account_id: int) -> AccountSubject | None:
    return db.scalar(
        select(AccountSubject).where(AccountSubject.tenant_id == tenant_id, AccountSubject.id == account_id)
    )


def account_code_exists(db: Session, tenant_id: int, code: str, exclude_id: int | None = None) -> bool:
    stmt = select(AccountSubject.id).where(AccountSubject.tenant_id == tenant_id, AccountSubject.code == code)
    if exclude_id:
        stmt = stmt.where(AccountSubject.id != exclude_id)
    return db.scalar(stmt) is not None


def account_has_vouchers(db: Session, tenant_id: int, account_id: int) -> bool:
    return (
        db.scalar(
            select(VoucherEntry.id).where(
                VoucherEntry.tenant_id == tenant_id,
                VoucherEntry.account_subject_id == account_id,
            ).limit(1)
        )
        is not None
    )


def create_account(db: Session, tenant_id: int, data: dict) -> AccountSubject:
    acct = AccountSubject(tenant_id=tenant_id, **data)
    db.add(acct)
    db.flush()
    return acct


def update_account(db: Session, acct: AccountSubject, data: dict) -> AccountSubject:
    for k, v in data.items():
        if v is not None and hasattr(acct, k):
            setattr(acct, k, v)
    db.flush()
    return acct


def delete_account(db: Session, acct: AccountSubject) -> None:
    db.delete(acct)
    db.flush()


# ---------- 凭证 ----------
def list_vouchers(
    db: Session,
    tenant_id: int,
    *,
    period: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Voucher]:
    stmt = select(Voucher).where(Voucher.tenant_id == tenant_id)
    if period:
        stmt = stmt.where(Voucher.period == period)
    if status:
        stmt = stmt.where(Voucher.status == status)
    if date_from:
        stmt = stmt.where(Voucher.voucher_date >= date_from)
    if date_to:
        stmt = stmt.where(Voucher.voucher_date <= date_to)
    stmt = stmt.order_by(Voucher.voucher_date.desc(), Voucher.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_voucher(db: Session, tenant_id: int, voucher_id: int) -> Voucher | None:
    return db.scalar(
        select(Voucher)
        .where(Voucher.tenant_id == tenant_id, Voucher.id == voucher_id)
        .options(selectinload(Voucher.entries))
    )


def voucher_code_exists(db: Session, tenant_id: int, code: str) -> bool:
    return db.scalar(select(Voucher.id).where(Voucher.tenant_id == tenant_id, Voucher.code == code)) is not None


def _entry_rows(tenant_id: int, entries: list[dict]) -> list[VoucherEntry]:
    return [
        VoucherEntry(
            tenant_id=tenant_id,
            line_no=i,
            account_subject_id=e["account_subject_id"],
            summary=e.get("summary"),
            debit_amount=e.get("debit_amount") or Decimal("0"),
            credit_amount=e.get("credit_amount") or Decimal("0"),
            party_type=e.get("party_type"),
            party_id=e.get("party_id"),
        )
        for i, e in enumerate(entries, start=1)
    ]


def create_voucher(
    db: Session,
    tenant_id: int,
    *,
    code: str,
    voucher_date: date,
    voucher_type: str,
    summary: str | None,
    amount: Decimal,
    period: str,
    entries: list[dict],
    source_type: str | None = None,
    source_id: int | None = None,
    created_by: int | None,
) -> Voucher:
    v = Voucher(
        tenant_id=tenant_id,
        code=code,
        voucher_date=voucher_date,
        voucher_type=voucher_type,
        summary=summary,
        amount=amount,
        period=period,
        status="draft",
        source_type=source_type,
        source_id=source_id,
        created_by=created_by,
    )
    v.entries = _entry_rows(tenant_id, entries)
    db.add(v)
    db.flush()
    return v


def update_voucher(db: Session, v: Voucher, data: dict) -> Voucher:
    for k, val in data.items():
        if k == "entries":
            continue
        if val is not None and hasattr(v, k):
            setattr(v, k, val)
    if "entries" in data and data["entries"] is not None:
        v.entries.clear()
        v.entries = _entry_rows(v.tenant_id, data["entries"])
        v.amount = sum(
            (e.debit_amount or Decimal("0")) for e in v.entries
        )
    db.flush()
    return v


def set_voucher_status(db: Session, v: Voucher, status: str, posted_by: int | None = None) -> Voucher:
    v.status = status
    if status == "posted":
        v.posted_by = posted_by
        v.posted_at = datetime.now()
    else:
        v.posted_by = None
        v.posted_at = None
    db.flush()
    return v


# ---------- 试算平衡 ----------
def trial_balance(db: Session, tenant_id: int, period: str) -> list[dict]:
    """科目期初 + 本期借贷汇总 → 期末余额。period: YYYY-MM"""
    accounts = list_accounts(db, tenant_id)
    stmt = (
        select(
            VoucherEntry.account_subject_id,
            func.coalesce(func.sum(VoucherEntry.debit_amount), 0),
            func.coalesce(func.sum(VoucherEntry.credit_amount), 0),
        )
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .where(
            Voucher.tenant_id == tenant_id,
            Voucher.status == "posted",
            Voucher.period == period,
        )
        .group_by(VoucherEntry.account_subject_id)
    )
    rows = {r[0]: (r[1], r[2]) for r in db.execute(stmt).all()}
    out = []
    for acct in accounts:
        debit, credit = rows.get(acct.id, (Decimal("0"), Decimal("0")))
        opening = acct.opening_balance or Decimal("0")
        if acct.direction == "debit":
            ending = opening + (debit or Decimal("0")) - (credit or Decimal("0"))
        else:
            ending = opening + (credit or Decimal("0")) - (debit or Decimal("0"))
        out.append(
            {
                "account_id": acct.id,
                "code": acct.code,
                "name": acct.name,
                "subject_type": acct.subject_type,
                "direction": acct.direction,
                "opening_balance": float(opening),
                "debit_amount": float(debit or 0),
                "credit_amount": float(credit or 0),
                "ending_balance": float(ending),
            }
        )
    return out


def balance_sheet(db: Session, tenant_id: int, period: str) -> dict:
    """按科目类型汇总资产/负债/权益（期末余额，方向符号化）"""
    tb = trial_balance(db, tenant_id, period)
    assets = 0.0
    liabilities = 0.0
    equity = 0.0
    for row in tb:
        val = row["ending_balance"]
        if row["subject_type"] == "asset":
            assets += val
        elif row["subject_type"] == "liability":
            liabilities += val
        elif row["subject_type"] == "equity":
            equity += val
    return {
        "period": period,
        "assets": round(assets, 2),
        "liabilities": round(liabilities, 2),
        "equity": round(equity, 2),
        "balance": round(assets - liabilities - equity, 2),
    }
