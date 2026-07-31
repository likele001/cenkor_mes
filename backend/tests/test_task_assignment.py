"""工序多人派工与报工上限"""

import pytest
from sqlalchemy.orm import Session

from app.crud.task_assignment import (
    replace_task_assignments,
    sum_user_reported_qty,
    validate_report_qty_limit,
)
from app.models.report import Report
from app.models.task import Task
from app.models.work_order import WorkOrder


def _make_task(session: Session, tenant, customer, sku, process, code_suffix: str, planned_qty: int = 100) -> Task:
    from app.models.order import Order, OrderItem

    o = Order(tenant_id=tenant.id, customer_id=customer.id, code=f"ORD-ASSIGN-{code_suffix}", status="confirmed")
    session.add(o)
    session.flush()
    oi = OrderItem(tenant_id=tenant.id, order_id=o.id, line_no=1, sku_id=sku.id, qty=planned_qty)
    session.add(oi)
    session.flush()
    wo = WorkOrder(
        tenant_id=tenant.id,
        order_id=o.id,
        order_item_id=oi.id,
        product_id=sku.product_id,
        sku_id=sku.id,
        qty=planned_qty,
        status="open",
    )
    session.add(wo)
    session.flush()
    task = Task(
        tenant_id=tenant.id,
        work_order_id=wo.id,
        process_id=process.id,
        seq=1,
        task_code=f"TK-ASSIGN-{code_suffix}",
        planned_qty=planned_qty,
        status="pending",
    )
    session.add(task)
    session.flush()
    return task


def test_replace_assignments_duplicate_user(session: Session, tenant, customer, test_user, sku, process):
    task = _make_task(session, tenant, customer, sku, process, "dup", 50)
    with pytest.raises(ValueError, match="不能重复"):
        replace_task_assignments(
            session,
            tenant_id=tenant.id,
            task=task,
            items=[
                {"user_id": test_user.id, "assigned_qty": 30},
                {"user_id": test_user.id, "assigned_qty": 25},
            ],
            dispatcher_user_id=test_user.id,
        )


def test_replace_assignments_exceed_planned(session: Session, tenant, customer, test_user, sku, process):
    task = _make_task(session, tenant, customer, sku, process, "exceed", 50)
    with pytest.raises(ValueError, match="不能超过"):
        replace_task_assignments(
            session,
            tenant_id=tenant.id,
            task=task,
            items=[{"user_id": test_user.id, "assigned_qty": 60}],
            dispatcher_user_id=test_user.id,
        )


def test_report_qty_limit(session: Session, tenant, customer, test_user, sku, process):
    task = _make_task(session, tenant, customer, sku, process, "report", 50)
    replace_task_assignments(
        session,
        tenant_id=tenant.id,
        task=task,
        items=[{"user_id": test_user.id, "assigned_qty": 20}],
        dispatcher_user_id=test_user.id,
    )
    session.add(
        Report(
            tenant_id=tenant.id,
            task_id=task.id,
            report_user_id=test_user.id,
            good_qty=15,
            bad_qty=0,
            status="submitted",
        )
    )
    session.flush()
    assert sum_user_reported_qty(session, tenant.id, task.id, test_user.id) == 15
    with pytest.raises(ValueError, match="超出派工上限"):
        validate_report_qty_limit(
            session,
            tenant_id=tenant.id,
            task=task,
            user_id=test_user.id,
            good_qty=10,
            bad_qty=0,
        )
    validate_report_qty_limit(
        session,
        tenant_id=tenant.id,
        task=task,
        user_id=test_user.id,
        good_qty=5,
        bad_qty=0,
    )
