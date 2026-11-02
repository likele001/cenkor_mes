# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""对账单核销：锁行后校验余额，重复/超额核销必须被拦下。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.crud.locking import lock_row
from app.crud.statement_payment import balance_of, create_payment
from app.models.finance import Statement
from app.models.material import Supplier
from app.models.supplier_statement import SupplierStatement


def _statement(session, customer, *, code="CS-1", total="1000", status="confirmed") -> Statement:
    stmt = Statement(
        customer_id=customer.id,
        code=code,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        total_amount=Decimal(total),
        paid_amount=Decimal("0"),
        status=status,
    )
    session.add(stmt)
    session.flush()
    return stmt


def test_partial_and_full_payment_update_statement(session, customer, test_user):
    stmt = _statement(session, customer, total="1000")

    create_payment(session, statement_type="statement", statement_id=stmt.id,
                   amount=Decimal("300"), created_by=test_user.id)
    session.refresh(stmt)
    assert stmt.status == "partial"
    assert Decimal(str(stmt.paid_amount)) == Decimal("300")

    create_payment(session, statement_type="statement", statement_id=stmt.id,
                   amount=Decimal("700"), created_by=test_user.id)
    session.refresh(stmt)
    assert stmt.status == "paid"
    assert balance_of(stmt) == Decimal("0")


def test_overpayment_is_rejected_and_balance_untouched(session, customer):
    stmt = _statement(session, customer, total="100")

    with pytest.raises(ValueError, match="超过未结余额"):
        create_payment(session, statement_type="statement", statement_id=stmt.id, amount=Decimal("150"))

    session.refresh(stmt)
    assert Decimal(str(stmt.paid_amount)) == Decimal("0")
    assert stmt.status == "confirmed"


def test_draft_and_paid_statements_reject_payment(session, customer):
    draft = _statement(session, customer, code="CS-D", status="draft")
    with pytest.raises(ValueError, match="需先确认"):
        create_payment(session, statement_type="statement", statement_id=draft.id, amount=Decimal("1"))

    paid = _statement(session, customer, code="CS-P", total="10", status="paid")
    with pytest.raises(ValueError, match="已结清"):
        create_payment(session, statement_type="statement", statement_id=paid.id, amount=Decimal("1"))


def test_missing_statement_is_rejected(session):
    with pytest.raises(ValueError, match="对账单不存在"):
        create_payment(session, statement_type="statement", statement_id=99999, amount=Decimal("1"))


def test_supplier_statement_payment_uses_ap_flow(session):
    supplier = Supplier(code="SUP-1", name="测试供应商")
    session.add(supplier)
    session.flush()
    stmt = SupplierStatement(
        supplier_id=supplier.id,
        code="SS-1",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        total_amount=Decimal("500"),
        paid_amount=Decimal("0"),
        status="confirmed",
    )
    session.add(stmt)
    session.flush()

    payment = create_payment(session, statement_type="supplier_statement",
                             statement_id=stmt.id, amount=Decimal("500"))
    session.refresh(stmt)
    assert payment.party_type == "supplier"
    assert payment.party_id == supplier.id
    assert stmt.status == "paid"


def test_lock_row_returns_none_for_missing_and_refreshes(session, customer):
    assert lock_row(session, Statement, 123456) is None

    stmt = _statement(session, customer)
    stmt.paid_amount = Decimal("42")
    session.flush()
    same = lock_row(session, Statement, stmt.id)
    assert same is not None
    assert same.id == stmt.id
    assert Decimal(str(same.paid_amount)) == Decimal("42")
