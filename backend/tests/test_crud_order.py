"""订单/工单/任务 核心流程测试"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.order import (
    confirm_order,
    create_order,
    create_work_orders_for_order,
    get_order_by_id,
    list_orders,
    update_order_items,
)
from app.crud.production_plan import create_plan, release_plan
from app.crud.work_order import get_work_order_by_id
from app.models.work_order import WorkOrder


def test_create_order(tenant, customer, sku, session: Session):
    order = create_order(
        session, tenant_id=tenant.id, customer_id=customer.id,
        code="ORD-TEST", due_date=None, remark="test",
        items=[(1, sku.id, 10, None)],
    )
    session.flush()
    assert order.id > 0
    assert order.code == "ORD-TEST"
    assert order.status == "draft"

    fetched = get_order_by_id(session, tenant_id=tenant.id, order_id=order.id)
    assert fetched is not None
    assert fetched.customer_id == customer.id


def test_confirm_order_does_not_generate_work_orders(tenant, test_user, customer, sku, process, process_route, process_price, session: Session):
    order = create_order(
        session, tenant_id=tenant.id, customer_id=customer.id,
        code="ORD-CONFIRM", due_date=None, remark=None,
        items=[(1, sku.id, 20, None)],
    )
    session.flush()

    confirm_order(session, order=order, confirmer_user_id=test_user.id)
    session.flush()
    assert order.status == "confirmed"

    wo_id = session.scalar(
        select(WorkOrder.id).where(WorkOrder.tenant_id == tenant.id, WorkOrder.order_id == order.id).limit(1)
    )
    assert wo_id is None


def test_release_plan_generates_work_orders(
    tenant, test_user, customer, sku, process, process_route, process_price, session: Session
):
    order = create_order(
        session, tenant_id=tenant.id, customer_id=customer.id,
        code="ORD-RELEASE", due_date=None, remark=None,
        items=[(1, sku.id, 20, None)],
    )
    session.flush()
    confirm_order(session, order=order, confirmer_user_id=test_user.id)
    session.flush()

    plan = create_plan(
        session,
        tenant_id=tenant.id,
        order_id=order.id,
        code="PLN-TEST",
        status="planned",
        start_date=None,
        end_date=None,
        work_days=None,
        remark=None,
        created_by=test_user.id,
    )
    session.flush()

    result = release_plan(
        session,
        tenant_id=tenant.id,
        plan=plan,
        releaser_user_id=test_user.id,
        allow_shortage=True,
    )
    session.flush()
    assert result["work_order_count"] >= 1
    assert order.status == "producing"
    assert plan.status == "in_progress"

    wo = session.scalar(select(WorkOrder).where(WorkOrder.tenant_id == tenant.id, WorkOrder.order_id == order.id))
    assert wo is not None
    wo_detail = get_work_order_by_id(session, tenant_id=tenant.id, work_order_id=wo.id, with_tasks=True)
    assert wo_detail is not None
    assert len(wo_detail.tasks) >= 1
    assert wo_detail.tasks[0].process_id == process.id


def test_release_plan_syncs_when_work_orders_exist(
    tenant, test_user, customer, sku, process, process_route, process_price, session: Session
):
    """订单已是生产中且已有工单，计划仍为「计划中」时，下发应同步而非报错。"""
    from app.crud.order import create_work_orders_for_order

    order = create_order(
        session,
        tenant_id=tenant.id,
        customer_id=customer.id,
        code="ORD-SYNC",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 10, None)],
    )
    session.flush()
    confirm_order(session, order=order, confirmer_user_id=test_user.id)
    create_work_orders_for_order(session, tenant_id=tenant.id, order=order)
    order.status = "producing"
    session.flush()

    plan = create_plan(
        session,
        tenant_id=tenant.id,
        order_id=order.id,
        code="PLN-SYNC",
        status="planned",
        start_date=None,
        end_date=None,
        work_days=None,
        remark=None,
        created_by=test_user.id,
    )
    session.flush()

    result = release_plan(
        session,
        tenant_id=tenant.id,
        plan=plan,
        releaser_user_id=test_user.id,
        allow_shortage=True,
    )
    assert result.get("synced") is True
    assert plan.status == "in_progress"
    assert result["work_order_count"] >= 1


def test_update_draft_order_items(tenant, customer, sku, session: Session):
    order = create_order(
        session,
        tenant_id=tenant.id,
        customer_id=customer.id,
        code="ORD-UPD-DRAFT",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 5, None)],
    )
    session.flush()
    item_id = order.items[0].id
    update_order_items(
        session,
        order,
        [(item_id, 1, sku.id, 12, "改数量")],
    )
    session.flush()
    refreshed = get_order_by_id(session, tenant_id=tenant.id, order_id=order.id, with_items=True)
    assert refreshed is not None
    assert len(refreshed.items) == 1
    assert refreshed.items[0].qty == 12
    assert refreshed.items[0].remark == "改数量"


def test_update_confirmed_order_qty_syncs_work_order(
    tenant, test_user, customer, sku, process, process_route, process_price, session: Session
):
    order = create_order(
        session,
        tenant_id=tenant.id,
        customer_id=customer.id,
        code="ORD-UPD-CONF",
        due_date=None,
        remark=None,
        items=[(1, sku.id, 10, None)],
    )
    session.flush()
    confirm_order(session, order=order, confirmer_user_id=test_user.id)
    session.flush()
    plan = create_plan(
        session,
        tenant_id=tenant.id,
        order_id=order.id,
        code="PLN-UPD",
        status="planned",
        start_date=None,
        end_date=None,
        work_days=None,
        remark=None,
        created_by=test_user.id,
    )
    session.flush()
    release_plan(session, tenant_id=tenant.id, plan=plan, releaser_user_id=test_user.id, allow_shortage=True)
    session.flush()
    item = order.items[0]
    update_order_items(session, order, [(item.id, 1, sku.id, 15, None)])
    session.flush()
    wo = session.scalar(
        select(WorkOrder).where(WorkOrder.tenant_id == tenant.id, WorkOrder.order_item_id == item.id)
    )
    assert wo is not None
    assert wo.qty == 15
    wo_detail = get_work_order_by_id(session, tenant_id=tenant.id, work_order_id=wo.id, with_tasks=True)
    assert wo_detail is not None
    assert all(t.planned_qty == 15 for t in wo_detail.tasks)


def test_tenant_isolation_for_orders(tenant, customer, sku, session: Session):
    create_order(session, tenant_id=tenant.id, customer_id=customer.id, code="ORD-ISO", due_date=None, remark=None, items=[(1, sku.id, 1, None)])
    session.flush()
    assert len(list_orders(session, tenant_id=tenant.id)) >= 1
    assert len(list_orders(session, tenant_id=9999)) == 0
