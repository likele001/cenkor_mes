# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""第四批·应收口径统一：核销、计提、现金流水必须各归各位。

修的是三套账各算各的：
- 管理端「标记已收款」只翻状态不记流水，总账里一分钱没见过；
- H5 客户点「我已付款」反而替我方记了一笔现金收入，还不回写 paid_amount；
- 老板看板回款率把「确认应收」的计提行当成到账，单子一确认回款率就 100%。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin.finance.router import profit_api
from app.crud import statement_payment as sp_crud
from app.crud.exec_dashboard import PeriodRange, get_collection_rate
from app.crud.supplier_statement import get_supplier_payables
from app.models.customer import Customer
from app.models.finance import Statement
from app.models.finance_ledger import FinanceLedger
from app.models.material import Supplier
from app.models.notification import Notification
from app.models.order import Order
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.statement_payment import StatementPayment
from app.models.supplier_statement import SupplierStatement
from app.models.user import User, user_roles

TOTAL = Decimal("1000.00")


# ────────────────────────── 测试脚手架 ──────────────────────────


def _cash_rows(db: Session, statement_id: int, category: str) -> list[FinanceLedger]:
    return list(
        db.scalars(
            select(FinanceLedger).where(
                FinanceLedger.statement_id == statement_id,
                FinanceLedger.category == category,
            )
        ).all()
    )


def _cash_total(db: Session, statement_id: int, category: str) -> Decimal:
    return Decimal(
        str(
            db.scalar(
                select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
                    FinanceLedger.statement_id == statement_id,
                    FinanceLedger.category == category,
                )
            )
            or 0
        )
    )


@pytest.fixture
def ar_statement(session: Session, customer: Customer) -> Statement:
    stmt = Statement(
        customer_id=customer.id,
        code="ST-P4-001",
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        total_amount=TOTAL,
        status="confirmed",
    )
    session.add(stmt)
    session.flush()
    return stmt


@pytest.fixture
def supplier(session: Session) -> Supplier:
    s = Supplier(code="S001", name="测试供应商", is_active=True)
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def ap_statement(session: Session, supplier: Supplier) -> SupplierStatement:
    stmt = SupplierStatement(
        supplier_id=supplier.id,
        code="PST-P4-001",
        total_amount=Decimal("600.00"),
        status="confirmed",
    )
    session.add(stmt)
    session.flush()
    return stmt


# ────────────────────────── 1. 计提与现金分家 ──────────────────────────


def test_confirm_writes_accrual_row_not_cash(session: Session, ar_statement: Statement, test_user: User):
    sp_crud.create_accrual_ledger(
        session,
        statement_type="statement",
        stmt=ar_statement,
        biz_date=date.today(),
        created_by=test_user.id,
        remark=f"客户对账单{ar_statement.code}确认应收",
    )
    assert [x.direction for x in _cash_rows(session, ar_statement.id, "ar")] == ["in"]
    assert _cash_total(session, ar_statement.id, "ar") == TOTAL
    # 确认对账单不是收到钱
    assert _cash_rows(session, ar_statement.id, "receipt") == []
    assert Decimal(str(ar_statement.paid_amount)) == Decimal("0")


def test_payment_writes_cash_row_and_rollsup(session: Session, ar_statement: Statement, test_user: User):
    sp_crud.create_payment(
        session,
        statement_type="statement",
        statement_id=ar_statement.id,
        amount=Decimal("300"),
        method="transfer",
        created_by=test_user.id,
    )
    assert Decimal(str(ar_statement.paid_amount)) == Decimal("300")
    assert ar_statement.status == "partial"
    assert _cash_total(session, ar_statement.id, "receipt") == Decimal("300")


def test_settle_only_closes_the_remaining_balance(session: Session, ar_statement: Statement, test_user: User):
    """先收 300 再整单结清：现金流水合计必须是 1000，不能又是 300 又是 1000。"""
    sp_crud.create_payment(
        session, statement_type="statement", statement_id=ar_statement.id, amount=Decimal("300"), created_by=test_user.id
    )
    p = sp_crud.settle_statement(
        session, statement_type="statement", statement_id=ar_statement.id, created_by=test_user.id
    )
    assert Decimal(str(p.amount)) == Decimal("700")
    assert ar_statement.status == "paid"
    assert Decimal(str(ar_statement.paid_amount)) == TOTAL
    assert _cash_total(session, ar_statement.id, "receipt") == TOTAL


def test_settle_is_idempotent(session: Session, ar_statement: Statement, test_user: User):
    sp_crud.settle_statement(session, statement_type="statement", statement_id=ar_statement.id, created_by=test_user.id)
    again = sp_crud.settle_statement(
        session, statement_type="statement", statement_id=ar_statement.id, created_by=test_user.id
    )
    assert again is None
    assert len(_cash_rows(session, ar_statement.id, "receipt")) == 1


def test_settle_requires_confirmed_statement(session: Session, ar_statement: Statement, test_user: User):
    ar_statement.status = "draft"
    session.flush()
    with pytest.raises(ValueError):
        sp_crud.settle_statement(
            session, statement_type="statement", statement_id=ar_statement.id, created_by=test_user.id
        )
    assert session.scalar(select(func.count(StatementPayment.id))) == 0


def test_reverse_appends_negative_cash_row(session: Session, ar_statement: Statement, test_user: User):
    """冲销不删流水：现金台账留得住「曾经记过一笔」的痕迹。"""
    p = sp_crud.create_payment(
        session, statement_type="statement", statement_id=ar_statement.id, amount=Decimal("400"), created_by=test_user.id
    )
    sp_crud.reverse_payment(session, p.id, created_by=test_user.id)
    session.flush()
    rows = _cash_rows(session, ar_statement.id, "receipt")
    assert len(rows) == 2
    assert _cash_total(session, ar_statement.id, "receipt") == Decimal("0")
    assert session.scalar(
        select(func.count()).select_from(StatementPayment).where(StatementPayment.id == p.id)
    ) == 0
    assert Decimal(str(ar_statement.paid_amount)) == Decimal("0")
    assert ar_statement.status == "confirmed"


# ────────────────────────── 2. 应付同一套出口 ──────────────────────────


def test_ap_settle_writes_out_payment_and_updates_statement(session: Session, ap_statement: SupplierStatement, test_user: User):
    sp_crud.create_accrual_ledger(
        session,
        statement_type="supplier_statement",
        stmt=ap_statement,
        biz_date=date.today(),
        created_by=test_user.id,
        remark=f"供应商对账单{ap_statement.code}确认应付",
    )
    sp_crud.settle_statement(
        session, statement_type="supplier_statement", statement_id=ap_statement.id, created_by=test_user.id
    )
    assert ap_statement.status == "paid"
    assert Decimal(str(ap_statement.paid_amount)) == Decimal("600.00")
    assert _cash_total(session, ap_statement.id, "ap") == Decimal("600.00")
    assert _cash_total(session, ap_statement.id, "payment") == Decimal("600.00")


def test_payables_summary_reads_statement_paid_amount(session: Session, supplier: Supplier, ap_statement: SupplierStatement, test_user: User):
    """应付汇总别再绕过核销去 SUM 总账——两处口径必须同源。"""
    rows = {r["supplier_id"]: r for r in get_supplier_payables(session)}
    assert rows[supplier.id]["total_payable"] == 600.0
    assert rows[supplier.id]["paid_amount"] == 0.0

    sp_crud.create_payment(
        session,
        statement_type="supplier_statement",
        statement_id=ap_statement.id,
        amount=Decimal("200"),
        created_by=test_user.id,
    )
    rows = {r["supplier_id"]: r for r in get_supplier_payables(session)}
    assert rows[supplier.id]["total_payable"] == 600.0
    assert rows[supplier.id]["paid_amount"] == 200.0
    assert rows[supplier.id]["unpaid_amount"] == 400.0


# ────────────────────────── 3. 读数口径跟着改 ──────────────────────────


def test_profit_uses_accrual_rows(session: Session, ar_statement: Statement, ap_statement: SupplierStatement, test_user: User):
    """毛利按计提算：确认应收/应付即计收入成本，实际收付不再重复计入。"""
    sp_crud.create_accrual_ledger(
        session, statement_type="statement", stmt=ar_statement, biz_date=date.today(), created_by=test_user.id, remark="ar"
    )
    sp_crud.create_accrual_ledger(
        session,
        statement_type="supplier_statement",
        stmt=ap_statement,
        biz_date=date.today(),
        created_by=test_user.id,
        remark="ap",
    )
    sp_crud.create_payment(
        session, statement_type="statement", statement_id=ar_statement.id, amount=TOTAL, created_by=test_user.id
    )
    month = date.today().strftime("%Y-%m")
    data = profit_api(month=month, db=session, user=test_user)["data"]
    assert data["revenue"] == 1000.0
    assert data["cost"] == 600.0
    assert data["gross_profit"] == 400.0


@pytest.fixture
def confirmed_order(session: Session, customer: Customer) -> Order:
    o = Order(
        customer_id=customer.id,
        code="SO-P4-001",
        status="confirmed",
        amount=TOTAL,
        cost_amount=0,
        confirmed_at=datetime.now(),
    )
    session.add(o)
    session.flush()
    return o


def _period() -> PeriodRange:
    now = datetime.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_start = (start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return PeriodRange(start=start, end=end, prev_start=prev_start, prev_end=start)


def test_collection_rate_ignores_accrual(session: Session, confirmed_order: Order, ar_statement: Statement, test_user: User):
    """确认应收不等于收到钱：只有核销流水才算回款。"""
    sp_crud.create_accrual_ledger(
        session, statement_type="statement", stmt=ar_statement, biz_date=date.today(), created_by=test_user.id, remark="ar"
    )
    assert get_collection_rate(session, _period())["collected"] == 0.0

    sp_crud.create_payment(
        session, statement_type="statement", statement_id=ar_statement.id, amount=Decimal("250"), created_by=test_user.id
    )
    got = get_collection_rate(session, _period())
    assert got["collected"] == 250.0
    assert got["value"] == pytest.approx(25.0)


# ────────────────────────── 4. H5 端：客户声明不是核销 ──────────────────────────


def _make_user(db: Session, username: str) -> User:
    u = User(username=username, password_hash="x", is_active=True)
    db.add(u)
    db.flush()
    return u


def _grant_role(db: Session, user: User, role: Role, permission_code: str) -> None:
    perm = Permission(code=permission_code, name=permission_code)
    db.add(perm)
    db.flush()
    db.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.flush()


@pytest.fixture
def customer_user(session: Session, customer: Customer) -> User:
    u = _make_user(session, "cust-login")
    customer.user_id = u.id
    session.flush()
    return u


def test_h5_mark_paid_does_not_touch_the_ledger(
    session: Session, customer_user: User, ar_statement: Statement, admin_role: Role
):
    from app.api.h5.customer import my_statement_mark_paid_api

    fin_user = _make_user(session, "fin")
    _grant_role(session, fin_user, admin_role, "finance.manage")

    resp = my_statement_mark_paid_api(statement_id=ar_statement.id, db=session, user=customer_user)
    assert resp["data"]["status"] == "confirmed"
    assert resp["data"]["claimed"] is True
    assert Decimal(str(ar_statement.paid_amount)) == Decimal("0")
    assert session.scalar(select(func.count(StatementPayment.id))) == 0
    assert _cash_rows(session, ar_statement.id, "receipt") == []
    # 声明要落到财务的待办里，不然客户说了等于没说
    assert session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == fin_user.id, Notification.biz_type == "statement"
        )
    ) == 1


def test_h5_statement_ack_still_works(session: Session, customer_user: User, customer: Customer):
    """客户确认对账单（draft → confirmed）历史上会因 feishu_event 参数 TypeError 直接 500。"""
    from app.api.h5.customer import my_statement_ack_api

    stmt = Statement(customer_id=customer.id, code="ST-P4-DRAFT", total_amount=TOTAL, status="draft")
    session.add(stmt)
    session.flush()

    resp = my_statement_ack_api(statement_id=stmt.id, db=session, user=customer_user)
    assert resp["data"]["status"] == "confirmed"
    assert _cash_rows(session, stmt.id, "receipt") == []


def test_notify_users_with_permission_forwards_feishu_event(session: Session, admin_role: Role):
    """notify_users_with_permission 之前不接 feishu_event，客户提交售后/确认对账单都会 500。"""
    from app.crud.notification import notify_users_with_permission

    target = _make_user(session, "cm")
    _grant_role(session, target, admin_role, "customer.manage")

    n = notify_users_with_permission(
        session,
        permission_code="customer.manage",
        title="t",
        content="c",
        biz_type="after_sale",
        biz_id=1,
        feishu_event="after_sale.created",
    )
    assert n == 1
    assert session.scalar(select(func.count(Notification.id)).where(Notification.user_id == target.id)) == 1
