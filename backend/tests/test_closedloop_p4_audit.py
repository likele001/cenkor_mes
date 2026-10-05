# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""第四批·3 审批留痕：单据每次状态翻转都要留下「谁、什么时候、从哪到哪、为什么」。

此前订单/采购/入库/对账/工资条只把最后一次审核结果写在 confirmed_by、confirmed_at 上，
驳回过几次、谁驳回的、理由是什么，全被下一次覆盖掉；审批流表（ApprovalFlow）也只有模板没有实例。
现在统一追加进 approval_records：只写不改不删。
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin.approval.records import list_records_api
from app.crud.approval_record import list_records, record_status, status_action
from app.crud.finance import update_statement_status
from app.crud.order import confirm_order, reject_order, submit_order_for_review
from app.crud.purchase_order import confirm_purchase_order
from app.crud.salary_slip import pay_slip, reset_salary_slip_confirm, sign_salary_slip, unpay_slip
from app.crud.statement_payment import create_payment, reverse_payment
from app.crud.warehouse_entry import confirm_entry, create_entry
from app.models.approval_record import ApprovalRecord
from app.models.attachment import Attachment
from app.models.customer import Customer
from app.models.finance import Statement
from app.models.material import Material, Supplier
from app.models.order import Order, OrderItem
from app.models.purchase import PurchaseOrder
from app.models.salary_slip import SalarySlip
from app.models.sku import Sku
from app.models.user import User
from app.models.warehouse import Warehouse


# ────────────────────────── 测试脚手架 ──────────────────────────


def _trail(db: Session, biz_type: str, biz_id: int) -> list[ApprovalRecord]:
    """按时间正序返回某张单据的留痕。"""
    rows = list_records(db, biz_type=biz_type, biz_id=biz_id)[0]
    return list(reversed(rows))


def _draft_order(session: Session, customer: Customer, sku: Sku) -> Order:
    order = Order(customer_id=customer.id, code="SO-AUDIT-001", status="draft", amount=0, cost_amount=0)
    session.add(order)
    session.flush()
    session.add(
        OrderItem(order_id=order.id, line_no=1, sku_id=sku.id, qty=100, unit_price=Decimal("1.50"), subtotal=Decimal("150.00"))
    )
    session.flush()
    return order


@pytest.fixture
def supplier_obj(session: Session) -> Supplier:
    s = Supplier(code="SUP-AUDIT", name="留痕供应商", is_active=True)
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def purchase_order(session: Session, supplier_obj: Supplier) -> PurchaseOrder:
    po = PurchaseOrder(supplier_id=supplier_obj.id, code="PO-AUDIT-001", status="draft")
    session.add(po)
    session.flush()
    return po


@pytest.fixture
def confirmed_statement(session: Session, customer: Customer) -> Statement:
    stmt = Statement(
        customer_id=customer.id,
        code="ST-AUDIT-001",
        total_amount=Decimal("800.00"),
        status="confirmed",
    )
    session.add(stmt)
    session.flush()
    return stmt


@pytest.fixture
def warehouse(session: Session) -> Warehouse:
    w = Warehouse(code="WH-AUDIT", name="留痕仓", is_active=True)
    session.add(w)
    session.flush()
    return w


@pytest.fixture
def material(session: Session, sku: Sku) -> Material:
    m = Material(code="MT-AUDIT", name="留痕物料", sku_id=sku.id, is_active=True)
    session.add(m)
    session.flush()
    return m


# ────────────────────────── 1. 订单：提交/驳回/确认全留痕 ──────────────────────────


def test_order_lifecycle_writes_three_rows(session: Session, test_user: User, customer: Customer, sku: Sku):
    order = _draft_order(session, customer, sku)

    submit_order_for_review(session, order, operator_id=test_user.id, channel="h5")
    reject_order(session, order, "价格不对", operator_id=test_user.id)
    confirm_order(session, order, confirmer_user_id=test_user.id)

    rows = _trail(session, "order", order.id)
    assert [r.action for r in rows] == ["submit", "reject", "confirm"]
    assert [r.from_status for r in rows] == ["draft", "pending_confirm", "draft"]
    assert [r.to_status for r in rows] == ["pending_confirm", "draft", "confirmed"]
    assert rows[1].reason == "价格不对"
    assert rows[0].channel == "h5"
    # 姓名快照：不是等查的时候再关联出来的空字符串
    assert all(r.operator_name == "管理员" for r in rows)
    assert all(r.biz_code == order.code for r in rows)


def test_trail_row_cannot_be_updated(session: Session, test_user: User, customer: Customer, sku: Sku):
    order = _draft_order(session, customer, sku)
    confirm_order(session, order, confirmer_user_id=test_user.id)
    row = _trail(session, "order", order.id)[-1]

    # 建个保存点，让失败的 flush 只回滚到这儿，别把测试会话的外层事务一起废掉
    savepoint = session.begin_nested()
    row.to_status = "hacked"
    with pytest.raises(RuntimeError):
        session.flush()
    savepoint.rollback()
    assert session.get(ApprovalRecord, row.id).to_status == "confirmed"


def test_trail_row_cannot_be_deleted(session: Session, test_user: User, customer: Customer, sku: Sku):
    order = _draft_order(session, customer, sku)
    record_status(
        session,
        biz_type="order",
        biz_id=order.id,
        action="cancel",
        operator=test_user.id,
        from_status="draft",
        to_status="cancelled",
    )
    row = session.scalars(select(ApprovalRecord).where(ApprovalRecord.biz_id == order.id)).one()

    savepoint = session.begin_nested()
    with pytest.raises(RuntimeError):
        session.delete(row)
        session.flush()
    savepoint.rollback()
    assert session.get(ApprovalRecord, row.id) is not None


# ────────────────────────── 2. 采购单 / 入库单 ──────────────────────────


def test_purchase_order_confirm_is_traced(session: Session, test_user: User, purchase_order: PurchaseOrder):
    confirm_purchase_order(session, purchase_order, confirmer_user_id=test_user.id)
    rows = _trail(session, "purchase_order", purchase_order.id)
    assert [(r.action, r.from_status, r.to_status) for r in rows] == [("confirm", "draft", "confirmed")]


def test_warehouse_entry_confirm_is_traced(
    session: Session, test_user: User, warehouse: Warehouse, material: Material, sku: Sku
):
    entry = create_entry(
        session,
        code="WE-AUDIT-001",
        source_type="other",
        warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": 5}],
        created_by=test_user.id,
    )
    confirm_entry(session, entry, confirmed_by=test_user.id)

    rows = _trail(session, "warehouse_entry", entry.id)
    assert [r.action for r in rows] == ["confirm"]
    assert rows[0].operator_id == test_user.id
    assert json.loads(rows[0].detail)["total_qty"] == entry.total_qty


# ────────────────────────── 3. 对账单：确认、核销、冲销 ──────────────────────────


def test_statement_status_change_is_traced(session: Session, test_user: User, customer: Customer):
    stmt = Statement(customer_id=customer.id, code="ST-AUDIT-002", total_amount=Decimal("500.00"), status="draft")
    session.add(stmt)
    session.flush()

    update_statement_status(session, stmt, "confirmed", operator=test_user, action=status_action("confirmed"))
    rows = _trail(session, "statement", stmt.id)
    assert [(r.action, r.to_status, r.operator_id) for r in rows] == [("confirm", "confirmed", test_user.id)]


def test_payment_and_reversal_leave_two_rows(session: Session, test_user: User, confirmed_statement: Statement):
    p = create_payment(
        session,
        statement_type="statement",
        statement_id=confirmed_statement.id,
        amount=Decimal("300.00"),
        created_by=test_user.id,
    )
    reverse_payment(session, p.id, created_by=test_user.id)

    rows = _trail(session, "statement", confirmed_statement.id)
    assert [r.action for r in rows] == ["pay", "reverse"]
    assert json.loads(rows[0].detail)["amount"] == "300.00"
    assert json.loads(rows[1].detail)["amount"] == "-300.00"
    # 冲销不抹掉前一行——「曾经记过一次」本身就是需要保留的事实
    assert rows[0].to_status == "partial"
    assert rows[1].from_status == "partial"


# ────────────────────────── 4. 工资条：签收与发放两条线各自留痕 ──────────────────────────


@pytest.fixture
def slip_user(session: Session) -> User:
    u = User(username="worker-audit", password_hash="$2b$12$x", full_name="张三", is_active=True)
    session.add(u)
    session.flush()
    return u


def _sign(session: Session, user: User, month: str) -> None:
    att = Attachment(
        uploader_id=user.id,
        storage_key="sig/test.png",
        original_filename="sig.png",
        content_type="image/png",
        size=10,
        sha256="0" * 64,
    )
    session.add(att)
    session.flush()
    sign_salary_slip(session, user_id=user.id, month=month, attachment_id=att.id)


def test_sign_pay_unpay_each_leave_a_row(session: Session, test_user: User, slip_user: User):
    month = date.today().strftime("%Y-%m")
    _sign(session, slip_user, month)
    slip = session.scalar(
        select(SalarySlip).where(SalarySlip.user_id == slip_user.id, SalarySlip.month == month)
    )
    slip.net_amount = Decimal("1200.00")
    session.flush()

    pay_slip(session, slip, operator_id=test_user.id, remark="银行代发")
    unpay_slip(session, slip, operator_id=test_user.id, reason="金额录错")
    reset_salary_slip_confirm(session, slip.id, operator=test_user.id, reason="员工申诉")

    rows = _trail(session, "salary_slip", slip.id)
    assert [r.action for r in rows] == ["sign", "pay", "unpay", "reset"]
    assert rows[0].operator_id == slip_user.id  # 签收是员工自己
    assert rows[1].operator_id == test_user.id  # 发放是厂里财务
    assert rows[1].reason == "银行代发"
    assert rows[2].reason == "金额录错"
    assert rows[3].reason == "员工申诉"
    # 留痕时间跟着单据上的时间走，事后补录也不会错位
    assert rows[0].created_at is not None


# ────────────────────────── 5. 查询接口 ──────────────────────────


def test_records_api_returns_newest_first(session: Session, test_user: User, customer: Customer, sku: Sku):
    order = _draft_order(session, customer, sku)
    submit_order_for_review(session, order, operator_id=test_user.id)
    reject_order(session, order, "缺附件", operator_id=test_user.id)

    res = list_records_api(biz_type="order", biz_id=order.id, operator_id=None, action=None, offset=0, limit=50, db=session, user=test_user)
    data = res["data"]
    items = data["items"]
    assert data["total"] == 2
    assert [i["action"] for i in items] == ["reject", "submit"]  # 倒序：最新在前
    assert items[0]["reason"] == "缺附件"
    assert items[0]["operator_name"] == "管理员"


def test_records_api_rejects_bad_filters(session: Session, test_user: User):
    with pytest.raises(HTTPException) as e1:
        list_records_api(biz_type="whatever", biz_id=1, operator_id=None, action=None, offset=0, limit=50, db=session, user=test_user)
    assert e1.value.status_code == 400

    with pytest.raises(HTTPException) as e2:
        list_records_api(biz_type=None, biz_id=1, operator_id=None, action=None, offset=0, limit=50, db=session, user=test_user)
    assert e2.value.status_code == 400


def test_status_action_map():
    assert status_action("confirmed") == "confirm"
    assert status_action("paid") == "pay"
    assert status_action("canceled") == "cancel"
    assert status_action("in_producing") == "status_change"
