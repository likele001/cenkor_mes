# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""AR/AP 部分核销与账龄测试（CRUD 层，SQLite 内存库）。"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.crud import statement_payment as sp
from app.models.finance import Statement
from app.models.material import Supplier
from app.models.supplier_statement import SupplierStatement


def _ar(session, customer, code, total, status="confirmed", due_days=None):
    due = date.today() + timedelta(days=due_days) if due_days is not None else None
    s = Statement(
        customer_id=customer.id, code=code,
        total_amount=Decimal(str(total)), paid_amount=Decimal("0"),
        status=status, due_date=due, period_end=date.today(),
    )
    session.add(s)
    session.flush()
    return s


def test_partial_settlement_advances_status_and_balance(session, customer):
    s = _ar(session, customer, "ST-P1", 1000)
    p = sp.create_payment(session, statement_type="statement", statement_id=s.id,
                          amount=Decimal("400"), created_by=None)
    session.flush()
    assert p.amount == Decimal("400")
    assert s.paid_amount == Decimal("400")
    assert s.status == "partial"
    # 结清余款
    sp.create_payment(session, statement_type="statement", statement_id=s.id, amount=Decimal("600"))
    session.flush()
    assert s.paid_amount == Decimal("1000")
    assert s.status == "paid"


def test_overpayment_rejected(session, customer):
    s = _ar(session, customer, "ST-P2", 500)
    with pytest.raises(ValueError):
        sp.create_payment(session, statement_type="statement", statement_id=s.id, amount=Decimal("600"))


def test_payment_on_draft_rejected(session, customer):
    s = _ar(session, customer, "ST-P3", 500, status="draft")
    with pytest.raises(ValueError):
        sp.create_payment(session, statement_type="statement", statement_id=s.id, amount=Decimal("100"))


def test_reverse_payment_restores_balance(session, customer):
    s = _ar(session, customer, "ST-P4", 1000)
    p1 = sp.create_payment(session, statement_type="statement", statement_id=s.id, amount=Decimal("1000"))
    session.flush()
    assert s.status == "paid"
    sp.reverse_payment(session, p1.id)
    session.flush()
    assert s.paid_amount == Decimal("0")
    assert s.status == "confirmed"


def test_aging_buckets_overdue(session, customer):
    # 逾期 45 天 → 31_60 档；未到期 → not_due 档
    _ar(session, customer, "ST-A1", 800, due_days=-45)
    _ar(session, customer, "ST-A2", 200, due_days=10)
    res = sp.get_aging(session, "ar")
    assert res["total_balance"] == pytest.approx(1000.0)
    by_bucket = {b["bucket"]: b for b in res["buckets"]}
    assert by_bucket["31_60"]["count"] == 1
    assert by_bucket["31_60"]["balance"] == pytest.approx(800.0)
    assert by_bucket["not_due"]["balance"] == pytest.approx(200.0)
    item = next(i for i in res["items"] if i["code"] == "ST-A1")
    assert item["days_overdue"] == 45


def test_aging_excludes_paid(session, customer):
    s = _ar(session, customer, "ST-A3", 300, due_days=-100)
    sp.create_payment(session, statement_type="statement", statement_id=s.id, amount=Decimal("300"))
    session.flush()
    res = sp.get_aging(session, "ar")
    assert all(i["code"] != "ST-A3" for i in res["items"])


def test_ap_settlement_symmetric(session, customer):
    sup = Supplier(code="S001", name="测试供应商", is_active=True)
    session.add(sup)
    session.flush()
    ap = SupplierStatement(
        supplier_id=sup.id, code="AP-1", total_amount=Decimal("1200"),
        paid_amount=Decimal("0"), status="confirmed", due_date=date.today() - timedelta(days=5),
    )
    session.add(ap)
    session.flush()
    sp.create_payment(session, statement_type="supplier_statement", statement_id=ap.id, amount=Decimal("700"))
    session.flush()
    assert ap.status == "partial" and ap.paid_amount == Decimal("700")
    res = sp.get_aging(session, "ap")
    assert res["total_balance"] == pytest.approx(500.0)
    assert res["items"][0]["bucket"] == "1_30"
