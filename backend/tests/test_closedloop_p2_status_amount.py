# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""闭环体检第二批：状态与金额写点

Task.status / WorkOrder.status / Order.status+amount+cost_amount+actual_completed_at
以前只有读没有写，看板与老板报表因此恒为 0。这里锁住回写链路。
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud.order import confirm_order, create_order, get_order_by_id
from app.crud.report import calc_and_create_salary, create_report, update_report_status
from app.models.customer import Customer
from app.models.order import Order
from app.models.process_price import ProcessPrice
from app.models.production_plan import ProductionPlan
from app.models.sku import Sku
from app.models.task import Task
from app.models.user import User
from app.models.work_order import WorkOrder


@pytest.fixture
def producing_order(session: Session, order_item: tuple) -> Order:
    order, _item = order_item
    order.status = "producing"
    session.commit()
    return order


def _report(session: Session, task: Task, user: User, good: int):
    r = create_report(
        session,
        task_id=task.id,
        report_user_id=user.id,
        good_qty=good,
        bad_qty=0,
        remark=None,
        attachment_ids=None,
    )
    session.commit()
    return r


# ────────────────────────── 1. 报工 → 任务状态 ──────────────────────────

def test_submitted_report_marks_task_working(session: Session, producing_order, task: Task, test_user: User):
    _report(session, task, test_user, 30)
    session.refresh(task)
    assert task.status == "working", "提交报工后任务不能再显示「待处理」"


def test_partial_approval_keeps_task_working(session: Session, producing_order, task: Task, test_user: User):
    r = _report(session, task, test_user, 40)
    update_report_status(session, r, "leader_approved")
    update_report_status(session, r, "qc_approved")
    session.commit()
    session.refresh(task)
    assert task.status == "working", "只报了 40/100 不能算完工"
    session.refresh(producing_order)
    assert producing_order.status == "producing"
    assert producing_order.actual_completed_at is None


def test_full_approval_cascades_task_workorder_order(session: Session, producing_order, task: Task, test_user: User):
    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "leader_approved")
    update_report_status(session, r, "qc_approved")
    session.commit()

    wo = session.get(WorkOrder, task.work_order_id)
    session.refresh(task)
    session.refresh(wo)
    session.refresh(producing_order)

    assert task.status == "done"
    assert wo.status == "done"
    assert wo.started_at is not None and wo.finished_at is not None
    assert producing_order.status == "completed"
    assert producing_order.actual_completed_at is not None


def test_rejection_rolls_progress_back(session: Session, producing_order, task: Task, test_user: User):
    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "qc_approved")
    session.commit()
    session.refresh(producing_order)
    assert producing_order.status == "completed"

    update_report_status(session, r, "rejected")
    session.commit()
    session.refresh(task)
    session.refresh(producing_order)
    assert task.status != "done", "驳回后必须退回到未完成，否则看板永远显示完工"
    assert producing_order.status == "producing"
    assert producing_order.actual_completed_at is None


def test_work_order_hours_are_computed(session: Session, producing_order, task: Task, test_user: User):
    """工时来自工序节拍：100 件 × 10 分钟 = 16.67 小时。"""
    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "qc_approved")
    session.commit()
    wo = session.get(WorkOrder, task.work_order_id)
    assert float(wo.standard_hours) == pytest.approx(16.67, abs=0.01)
    assert float(wo.actual_hours) == pytest.approx(16.67, abs=0.01)


def test_plan_marked_done_when_order_completed(
    session: Session, producing_order, task: Task, test_user: User
):
    plan = ProductionPlan(
        order_id=producing_order.id,
        code="PP-DONE-1",
        status="in_progress",
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=1),
    )
    session.add(plan)
    session.commit()

    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "qc_approved")
    session.commit()
    session.refresh(plan)
    assert plan.status == "done"


# ────────────────────────── 2. 订单金额 ──────────────────────────

def test_create_order_computes_subtotal_and_amount(session: Session, customer: Customer, sku: Sku):
    order = create_order(
        session,
        customer_id=customer.id,
        code="SO-AMT-1",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 100, None, Decimal("2.5"))],
    )
    session.commit()
    item = get_order_by_id(session, order_id=order.id, with_items=True)
    assert float(item.items[0].unit_price) == 2.5
    assert float(item.items[0].subtotal) == 250.0
    assert float(item.amount) == 250.0


def test_amount_without_price_stays_zero(session: Session, customer: Customer, sku: Sku):
    """没填单价时金额为 0 — 不能用成本冒充收入。"""
    order = create_order(
        session,
        customer_id=customer.id,
        code="SO-AMT-2",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 100, None)],
    )
    session.commit()
    assert float(order.amount) == 0.0


def test_confirm_order_recalculates_amount(session: Session, customer: Customer, sku: Sku, test_user: User):
    from app.crud.order import update_order

    order = create_order(
        session,
        customer_id=customer.id,
        code="SO-AMT-3",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 10, None, Decimal("1.00"))],
    )
    session.commit()
    full = get_order_by_id(session, order_id=order.id, with_items=True)
    full.items[0].unit_price = Decimal("8.00")
    update_order(session, order=full)
    confirm_order(session, order=full, confirmer_user_id=test_user.id)
    session.commit()
    assert float(full.amount) == 80.0


def test_cost_amount_follows_generated_salary(session: Session, producing_order, task: Task, test_user: User, sku: Sku, process):
    session.add(ProcessPrice(sku_id=sku.id, process_id=process.id, unit_price=Decimal("1.5"), is_active=True))
    session.commit()

    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "leader_approved")
    update_report_status(session, r, "qc_approved")
    session.commit()

    from app.crud.report import calc_and_create_salary
    from app.services.production_rollup import recalc_order_cost

    calc_and_create_salary(session, report=r)
    recalc_order_cost(session, producing_order)
    session.commit()
    assert float(producing_order.cost_amount) == pytest.approx(150.0, abs=0.01)


# ────────────────────────── 3. 守门：不许再出现只读不写 ──────────────────────────

def test_rollup_hooked_into_report_and_unit_crud():
    import inspect as _inspect
    import pathlib

    for mod in ("app/crud/report.py", "app/crud/report_unit.py"):
        src = pathlib.Path(mod).read_text()
        assert "production_rollup" in src, f"{mod} 必须把状态变化传给汇总服务"

    from app.services.production_rollup import (
        recalc_order_amount,
        recalc_order_cost,
        sync_after_report,
        sync_after_unit,
        sync_order_progress,
        sync_task_status,
        sync_work_order_progress,
    )
    assert all(callable(f) for f in (
        recalc_order_amount, recalc_order_cost, sync_after_report,
        sync_after_unit, sync_order_progress, sync_task_status, sync_work_order_progress,
    ))


# ────────────────────────── 4. 金额入口一致：Excel 导入也带单价 ──────────────────────────

def _workbook_bytes(rows: list[list]) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_import_reads_sales_unit_price():
    from decimal import Decimal

    from app.services.order_import import parse_detail_lines

    raw = _workbook_bytes([
        ["序号", "产品名称", "型号名称", "数量", "单价", "行备注"],
        [1, "沙发", "三人位", 10, "12.5", ""],
        [2, "沙发", "双人位", 4, "", "未填价"],
        [3, "沙发", "单人位", 2, 8, ""],
    ])
    lines = parse_detail_lines(raw)
    assert [l.unit_price for l in lines] == [Decimal("12.5"), None, Decimal("8")]


def test_excel_import_template_documents_price_column():
    from io import BytesIO

    from openpyxl import load_workbook

    from app.services.order_import import build_import_template_bytes

    ws = load_workbook(BytesIO(build_import_template_bytes())).active
    header = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert "单价" in header, "模板必须教会用户填销售单价"


def test_import_price_tuple_feeds_order_amount(session, customer, product, sku):
    """导入路径的 5 元组（含单价）必须算进订单金额，而不是留 0。"""
    from decimal import Decimal

    from app.crud.order import create_order

    order = create_order(
        session,
        customer_id=customer.id,
        code="ORD-PRICE-1",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 10, None, Decimal("12.5")), (2, sku.id, 4, None, None)],
    )
    session.commit()
    assert order.amount == Decimal("125.00")
    assert [i.subtotal for i in order.items] == [Decimal("125.00"), Decimal("0")]


# ────────────────────────── 5. 老板看板真的有数 ──────────────────────────

def test_exec_dashboard_reads_rolled_up_metrics(
    session: Session, producing_order, task: Task, test_user: User, sku: Sku, process
):
    """汇总链写完的字段，必须能被供应商看板的 5 大指标读到。"""
    from datetime import datetime

    from app.crud.exec_dashboard import (
        get_exec_dashboard_summary,
        get_order_status_distribution,
        get_period_range,
        get_top_customers,
        get_top_skus,
    )
    from app.services.production_rollup import recalc_order_amount

    order = producing_order
    order.confirmed_at = datetime.now()
    order.due_date = date.today() + timedelta(days=2)
    order.items[0].unit_price = Decimal("10")
    recalc_order_amount(session, order)
    session.add(ProcessPrice(sku_id=sku.id, process_id=process.id, unit_price=Decimal("1.5"), is_active=True))
    session.commit()

    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "leader_approved")
    update_report_status(session, r, "qc_approved")
    calc_and_create_salary(session, report=r)
    session.commit()

    s = get_exec_dashboard_summary(session, "month")
    assert s["revenue"]["value"] == pytest.approx(1000.0, abs=0.01), "销售额=订单金额，不是工单数量"
    assert s["profit_margin"]["value"] == pytest.approx(85.0, abs=0.5), "毛利=(1000-150)/1000"
    assert s["delivery_rate"]["value"] == pytest.approx(100.0, abs=0.01), "actual_completed_at 没写时准交率恒为 0"
    assert s["capacity_utilization"]["value"] == pytest.approx(100.0, abs=1.0)

    pr = get_period_range("month")
    top_c = get_top_customers(session, period=pr, limit=5)
    assert top_c and top_c[0]["customer_name"] == "测试客户"
    assert top_c[0]["amount"] == pytest.approx(1000.0, abs=0.01)
    top_s = get_top_skus(session, period=pr, limit=5)
    assert top_s and top_s[0]["quantity"] == 100
    assert {"completed", "producing", "confirmed"} >= {d["status"] for d in get_order_status_distribution(session)}
    assert any(d["count"] for d in get_order_status_distribution(session))


def test_cancelled_work_order_is_not_resurrected(
    session: Session, producing_order, task: Task, test_user: User
):
    wo = session.get(WorkOrder, task.work_order_id)
    wo.status = "cancelled"
    session.commit()

    r = _report(session, task, test_user, 100)
    update_report_status(session, r, "qc_approved")
    session.commit()

    session.refresh(wo)
    session.refresh(producing_order)
    assert wo.status == "cancelled", "人工终止的工单不能被报工复活"
    assert producing_order.status != "completed", "唯一工单被取消，订单不能凭空判定完工"
    assert wo.standard_hours and float(wo.actual_hours or 0) > 0, "取消工单的已发生工时仍要如实统计"


def test_cancelled_line_does_not_block_order_completion(
    session: Session, producing_order, task: Task, test_user: User, sku: Sku, product
):
    """一行取消、其余完工 —— 订单必须能收尾，否则永远挂在生产中。"""
    from app.models.order import OrderItem
    from app.models.work_order import WorkOrder

    wo_alive = session.get(WorkOrder, task.work_order_id)
    wo_alive.status = "cancelled"
    extra_item = OrderItem(order_id=producing_order.id, line_no=2, sku_id=sku.id, qty=10,
                           unit_price=Decimal("1"), subtotal=Decimal("10"))
    session.add(extra_item)
    session.flush()
    wo2 = WorkOrder(order_id=producing_order.id, order_item_id=extra_item.id,
                    product_id=product.id, sku_id=sku.id, qty=10, status="open")
    session.add(wo2)
    session.flush()
    t2 = Task(work_order_id=wo2.id, process_id=task.process_id, seq=1,
              task_code="T-CORE-002", planned_qty=10, status="pending")
    session.add(t2)
    session.commit()

    r = _report(session, t2, test_user, 10)
    update_report_status(session, r, "qc_approved")
    session.commit()

    session.refresh(producing_order)
    session.refresh(wo2)
    assert wo2.status == "done"
    assert producing_order.status == "completed"
    assert producing_order.actual_completed_at is not None
