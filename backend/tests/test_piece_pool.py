"""套号池：派工预赋码 + 谁有空谁领下一套"""

import pytest
from sqlalchemy.orm import Session

from app.crud.process_flow import (
    auto_bind_piece_to_unit,
    claim_next_piece_for_task,
    ensure_work_order_piece_pool,
    list_pieces_for_work_order,
)
from app.crud.report_unit import get_next_draft_unit, submit_unit, sync_assignment_units
from app.crud.task_assignment import replace_task_assignments
from app.crud.tenant_setting import upsert_setting
from app.models.order import Order, OrderItem
from app.models.process import Process
from app.models.report_unit import ReportUnit
from app.models.task import Task
from app.models.user import User, user_roles
from app.models.work_order import WorkOrder
from app.services.report_mode_settings import KEY_DEFAULT_MODE


def _enable_unit_mode(session: Session, tenant_id: int) -> None:
    upsert_setting(session, tenant_id, KEY_DEFAULT_MODE, "unit")
    session.flush()


def _employee(session: Session, tenant, employee_role, suffix: str) -> User:
    u = User(
        tenant_id=tenant.id,
        username=f"emp_{suffix}",
        password_hash="x",
        full_name=f"员工{suffix}",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=employee_role.id))
    session.flush()
    return u


def _wo_with_tasks(
    session: Session,
    tenant,
    customer,
    sku,
    processes: list[Process],
    qty: int,
    suffix: str,
) -> tuple[WorkOrder, list[Task]]:
    o = Order(tenant_id=tenant.id, customer_id=customer.id, code=f"ORD-POOL-{suffix}", status="confirmed")
    session.add(o)
    session.flush()
    oi = OrderItem(tenant_id=tenant.id, order_id=o.id, line_no=1, sku_id=sku.id, qty=qty)
    session.add(oi)
    session.flush()
    wo = WorkOrder(
        tenant_id=tenant.id,
        order_id=o.id,
        order_item_id=oi.id,
        product_id=sku.product_id,
        sku_id=sku.id,
        qty=qty,
        status="open",
    )
    session.add(wo)
    session.flush()
    tasks: list[Task] = []
    for i, proc in enumerate(processes, start=1):
        t = Task(
            tenant_id=tenant.id,
            work_order_id=wo.id,
            process_id=proc.id,
            seq=i,
            task_code=f"TK-POOL-{suffix}-{i}",
            planned_qty=qty,
            status="pending",
        )
        session.add(t)
        session.flush()
        tasks.append(t)
    return wo, tasks


def test_dispatch_creates_piece_pool(session: Session, tenant, customer, sku, process, test_user):
    _enable_unit_mode(session, tenant.id)
    wo, tasks = _wo_with_tasks(session, tenant, customer, sku, [process], qty=5, suffix="pool")
    replace_task_assignments(
        session,
        tenant_id=tenant.id,
        task=tasks[0],
        items=[{"user_id": test_user.id, "assigned_qty": 5}],
        dispatcher_user_id=test_user.id,
    )
    pieces = list_pieces_for_work_order(session, tenant.id, wo.id)
    assert len(pieces) == 5
    assert all(p.product_code for p in pieces)
    assert all(p.status == "reserved" for p in pieces)


def test_two_workers_claim_different_pieces(
    session: Session, tenant, customer, sku, process, test_user, employee_role
):
    _enable_unit_mode(session, tenant.id)
    emp_b = _employee(session, tenant, employee_role, "b")
    wo, tasks = _wo_with_tasks(session, tenant, customer, sku, [process], qty=5, suffix="claim")
    replace_task_assignments(
        session,
        tenant_id=tenant.id,
        task=tasks[0],
        items=[
            {"user_id": test_user.id, "assigned_qty": 3},
            {"user_id": emp_b.id, "assigned_qty": 2},
        ],
        dispatcher_user_id=test_user.id,
    )
    from app.crud.task_assignment import get_assignment

    a1 = get_assignment(session, tenant.id, tasks[0].id, test_user.id)
    a2 = get_assignment(session, tenant.id, tasks[0].id, emp_b.id)
    assert a1 and a2
    u1 = get_next_draft_unit(session, tenant.id, a1.id)
    u2 = get_next_draft_unit(session, tenant.id, a2.id)
    assert u1 and u2

    p1 = auto_bind_piece_to_unit(session, tenant.id, u1, tasks[0])
    p2 = auto_bind_piece_to_unit(session, tenant.id, u2, tasks[0])
    assert p1.piece_no == 1
    assert p2.piece_no == 2
    assert p1.id != p2.id


def test_downstream_claims_after_prev_qc_approved(
    session: Session, tenant, customer, sku, process, test_user, employee_role
):
    _enable_unit_mode(session, tenant.id)
    p2 = Process(tenant_id=tenant.id, code="OP02", name="缝纫", workshop="车间", std_minutes=10, is_active=True)
    session.add(p2)
    session.flush()
    wo, tasks = _wo_with_tasks(session, tenant, customer, sku, [process, p2], qty=3, suffix="down")
    replace_task_assignments(
        session,
        tenant_id=tenant.id,
        task=tasks[0],
        items=[{"user_id": test_user.id, "assigned_qty": 3}],
        dispatcher_user_id=test_user.id,
    )
    from app.crud.task_assignment import get_assignment

    a1 = get_assignment(session, tenant.id, tasks[0].id, test_user.id)
    u1 = get_next_draft_unit(session, tenant.id, a1.id)
    piece = auto_bind_piece_to_unit(session, tenant.id, u1, tasks[0])
    submit_unit(
        session,
        unit=u1,
        result_type="good",
        employee_attachment_ids="1",
        remark=None,
    )
    u1.status = "qc_approved"
    session.flush()

    replace_task_assignments(
        session,
        tenant_id=tenant.id,
        task=tasks[1],
        items=[{"user_id": test_user.id, "assigned_qty": 3}],
        dispatcher_user_id=test_user.id,
    )
    a2 = get_assignment(session, tenant.id, tasks[1].id, test_user.id)
    u2 = get_next_draft_unit(session, tenant.id, a2.id)
    bound = claim_next_piece_for_task(session, tenant.id, tasks[1], u2)
    assert bound.id == piece.id
