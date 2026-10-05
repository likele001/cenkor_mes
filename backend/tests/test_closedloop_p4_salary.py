# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""第四批·2 工资落账：月份按报工那天归属，发放必须进总账。

修的是两处：
1. 工资明细的月份取的是「审核通过那一刻」的 now()——月底的活拖到下个月签字，
   工钱就跑到下个月工资条上，员工少拿一个月。
2. 工资条只有员工签收状态，压根没有「厂里付了没有」这一层，
   所以人力成本从来没进过现金总账，支出表永远缺一块。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.report import calc_and_create_salary
from app.crud.report_unit import calc_and_create_salary_for_unit
from app.crud.salary_slip import (
    ensure_salary_slip,
    month_payable_summary,
    pay_month,
    pay_slip,
    unpay_slip,
)
from app.models.finance_ledger import FinanceLedger
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.models.salary import SalaryItem
from app.models.salary_slip import SalarySlip
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import User

LAST_MONTH_DAY = (date.today().replace(day=1) - timedelta(days=1)).isoformat()


def _labor_rows(db: Session, slip_id: int) -> list[FinanceLedger]:
    return list(
        db.scalars(
            select(FinanceLedger).where(
                FinanceLedger.statement_type == "salary_slip",
                FinanceLedger.statement_id == slip_id,
                FinanceLedger.category == "labor",
            )
        ).all()
    )


def _labor_total(db: Session, slip_id: int) -> Decimal:
    return Decimal(
        str(
            db.scalar(
                select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
                    FinanceLedger.statement_type == "salary_slip",
                    FinanceLedger.statement_id == slip_id,
                    FinanceLedger.category == "labor",
                )
            )
            or 0
        )
    )


@pytest.fixture
def approved_report(session: Session, task: Task, test_user: User) -> Report:
    """上个月干的活，这个月才终审通过。"""
    r = Report(
        task_id=task.id,
        report_user_id=test_user.id,
        good_qty=10,
        bad_qty=0,
        status="qc_approved",
    )
    session.add(r)
    session.flush()
    r.created_at = datetime.fromisoformat(f"{LAST_MONTH_DAY}T09:00:00")
    session.flush()
    return r


@pytest.fixture
def approved_unit(session: Session, task: Task, assignment: TaskAssignment, test_user: User) -> ReportUnit:
    u = ReportUnit(
        task_assignment_id=assignment.id,
        task_id=task.id,
        user_id=test_user.id,
        unit_seq=1,
        result_type="good",
        status="qc_approved",
    )
    session.add(u)
    session.flush()
    u.submitted_at = datetime.fromisoformat(f"{LAST_MONTH_DAY}T10:00:00")
    session.flush()
    return u


# ────────────────────────── 1. 月份归属 ──────────────────────────


def test_piece_salary_month_follows_the_report_day(
    session: Session, approved_report: Report, process_price: ProcessPrice, sku: Sku, process: Process
):
    item = calc_and_create_salary(session, approved_report)
    assert item is not None
    assert item.month == LAST_MONTH_DAY[:7], "跨月审核不能把工资挪到审核那个月"
    assert str(item.work_date) == LAST_MONTH_DAY
    assert Decimal(str(item.amount)) == Decimal("15.00")


def test_unit_salary_month_follows_the_submit_day(session: Session, approved_unit: ReportUnit, process_price: ProcessPrice):
    item = calc_and_create_salary_for_unit(session, approved_unit)
    assert item is not None
    assert item.month == LAST_MONTH_DAY[:7]
    assert str(item.work_date) == LAST_MONTH_DAY


def test_slip_aggregates_into_the_work_month(session: Session, approved_report: Report, test_user: User, process_price: ProcessPrice):
    calc_and_create_salary(session, approved_report)
    month = LAST_MONTH_DAY[:7]
    slip = ensure_salary_slip(session, user_id=test_user.id, month=month)
    assert Decimal(str(slip.item_amount)) == Decimal("15.00")
    assert Decimal(str(slip.net_amount)) == Decimal("15.00")
    # 审核当月不该凭空冒出工资条
    this_month = date.today().strftime("%Y-%m")
    other = ensure_salary_slip(session, user_id=test_user.id, month=this_month)
    assert Decimal(str(other.net_amount)) == Decimal("0")


# ────────────────────────── 2. 发放落账 ──────────────────────────


@pytest.fixture
def slip(session: Session, test_user: User) -> SalarySlip:
    s = SalarySlip(
        user_id=test_user.id,
        month=date.today().strftime("%Y-%m"),
        item_amount=Decimal("2000"),
        net_amount=Decimal("2000"),
        total_qty=100,
        confirm_status="signed",
    )
    session.add(s)
    session.flush()
    return s


def test_pay_slip_writes_cash_ledger(session: Session, slip: SalarySlip, test_user: User):
    paid = pay_slip(session, slip, operator_id=test_user.id, remark="银行批次 001")
    assert paid.pay_status == "paid"
    assert paid.paid_at is not None
    assert paid.paid_by == test_user.id
    assert paid.paid_remark == "银行批次 001"
    rows = _labor_rows(session, slip.id)
    assert len(rows) == 1
    assert rows[0].direction == "out"
    assert rows[0].party_type == "employee"
    assert rows[0].party_id == slip.user_id
    assert _labor_total(session, slip.id) == Decimal("2000")


def test_pay_slip_twice_is_refused(session: Session, slip: SalarySlip, test_user: User):
    pay_slip(session, slip, operator_id=test_user.id)
    with pytest.raises(ValueError):
        pay_slip(session, slip, operator_id=test_user.id)
    assert _labor_total(session, slip.id) == Decimal("2000"), "重复发放不能把同一笔钱记两遍"


def test_rejected_slip_cannot_be_paid(session: Session, slip: SalarySlip, test_user: User):
    slip.confirm_status = "rejected"
    session.flush()
    with pytest.raises(ValueError):
        pay_slip(session, slip, operator_id=test_user.id)
    assert slip.pay_status == "unpaid"
    assert _labor_rows(session, slip.id) == []


def test_zero_slip_is_not_paid(session: Session, test_user: User):
    s = SalarySlip(user_id=test_user.id, month=date.today().strftime("%Y-%m"), net_amount=Decimal("0"))
    session.add(s)
    session.flush()
    with pytest.raises(ValueError):
        pay_slip(session, s, operator_id=test_user.id)


def _make_user(session: Session, username: str) -> User:
    u = User(username=username, password_hash="x", is_active=True)
    session.add(u)
    session.flush()
    return u


def test_pay_month_skips_paid_and_blocked(session: Session, slip: SalarySlip, test_user: User):
    pending = SalarySlip(
        user_id=_make_user(session, "emp2").id, month=slip.month, net_amount=Decimal("500"), confirm_status="pending"
    )
    rejected = SalarySlip(
        user_id=_make_user(session, "emp3").id, month=slip.month, net_amount=Decimal("800"), confirm_status="rejected"
    )
    session.add_all([pending, rejected])
    session.flush()

    paid = pay_month(session, month=slip.month, operator_id=test_user.id)
    assert {s.id for s in paid} == {slip.id, pending.id}, "拒签的不该发，其余按待发清单发"
    assert _labor_total(session, rejected.id) == Decimal("0")

    again = pay_month(session, month=slip.month, operator_id=test_user.id)
    assert again == [], "已发放的不重复发"
    assert _labor_total(session, slip.id) == Decimal("2000")


def test_unpay_appends_negative_row(session: Session, slip: SalarySlip, test_user: User):
    """撤销发放不删流水：现金台账留得住「曾经付过一次」的痕迹。"""
    pay_slip(session, slip, operator_id=test_user.id)
    unpay_slip(session, slip, operator_id=test_user.id, reason="金额算错")
    assert slip.pay_status == "unpaid"
    assert slip.paid_at is None
    assert len(_labor_rows(session, slip.id)) == 2
    assert _labor_total(session, slip.id) == Decimal("0")


def test_unpay_requires_paid_slip(session: Session, slip: SalarySlip, test_user: User):
    with pytest.raises(ValueError):
        unpay_slip(session, slip, operator_id=test_user.id)


def test_pay_summary_splits_paid_and_unpaid(session: Session, slip: SalarySlip, test_user: User):
    summary = month_payable_summary(session, slip.month)
    assert summary["unpaid_amount"] == 2000.0
    assert summary["paid_amount"] == 0.0
    pay_slip(session, slip, operator_id=test_user.id)
    summary = month_payable_summary(session, slip.month)
    assert summary["paid_amount"] == 2000.0
    assert summary["unpaid_amount"] == 0.0
    assert summary["paid_count"] == 1
