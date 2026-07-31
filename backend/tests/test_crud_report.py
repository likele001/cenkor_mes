"""报工 / 工资 核心逻辑测试"""

from sqlalchemy.orm import Session

from app.crud.order import create_order, confirm_order
from app.crud.report import create_report, calc_and_create_salary, get_salary_items, get_salary_summary
from app.crud.report import update_report_status, create_audit
from app.models.task import Task


def test_full_report_and_salary_flow(
    tenant, test_user, customer, sku, process, process_route, process_price, session: Session,
):
    """完整闭环：订单→确认→报工→审核→计薪"""
    # 1. 订单
    order = create_order(session, tenant_id=tenant.id, customer_id=customer.id, code="ORD-FLOW", due_date=None, remark=None, items=[(1, sku.id, 10, None)])
    session.flush()

    # 2. 确认订单后生成工单+任务
    confirm_order(session, order=order, confirmer_user_id=test_user.id)
    from app.crud.order import create_work_orders_for_order
    from app.crud.work_order import get_work_order_by_id

    wos = create_work_orders_for_order(session, tenant_id=tenant.id, order=order)
    session.flush()
    wo = get_work_order_by_id(session, tenant_id=tenant.id, work_order_id=wos[0].id, with_tasks=True)
    assert wo and wo.tasks
    task = wo.tasks[0]

    # 3. 派工
    task.assigned_user_id = test_user.id
    task.status = "working"
    session.flush()

    # 4. 报工
    report = create_report(session, tenant_id=tenant.id, task_id=task.id, report_user_id=test_user.id,
                           good_qty=8, bad_qty=2, remark="测试", attachment_ids=None)
    session.flush()
    assert report.status == "submitted"
    assert report.good_qty == 8

    # 5. 班组长初审
    create_audit(session, tenant_id=tenant.id, report_id=report.id, auditor_id=test_user.id, audit_level="leader", action="approve", reason=None)
    update_report_status(session, report, "leader_approved")
    session.flush()

    # 6. 终审+计薪
    create_audit(session, tenant_id=tenant.id, report_id=report.id, auditor_id=test_user.id, audit_level="qc", action="approve", reason=None)
    update_report_status(session, report, "qc_approved")
    session.flush()
    salary = calc_and_create_salary(session, tenant_id=tenant.id, report=report)
    session.flush()
    assert salary is not None
    assert float(salary.amount) == 12.0
    assert salary.good_qty == 8

    # 7. 验证工资明细
    items = get_salary_items(session, tenant_id=tenant.id, user_id=test_user.id)
    assert any(s.report_id == report.id and float(s.amount) == 12.0 for s in items)


def test_report_salary_calculation(tenant, test_user, customer, sku, process, process_route, process_price, session: Session):
    from app.models.order import Order, OrderItem
    o = Order(tenant_id=tenant.id, customer_id=customer.id, code="ORD-CALC", status="confirmed")
    session.add(o)
    session.flush()
    oi = OrderItem(tenant_id=tenant.id, order_id=o.id, line_no=1, sku_id=sku.id, qty=10)
    session.add(oi)
    session.flush()
    from app.crud.work_order import WorkOrder
    wo = WorkOrder(tenant_id=tenant.id, order_id=o.id, order_item_id=oi.id, product_id=sku.product_id, sku_id=sku.id, qty=10, status="open")
    session.add(wo)
    session.flush()
    task = Task(tenant_id=tenant.id, work_order_id=wo.id, process_id=process.id, seq=1,
                task_code="TK-CALC", planned_qty=10, status="working", assigned_user_id=test_user.id)
    session.add(task)
    session.flush()

    report = create_report(session, tenant_id=tenant.id, task_id=task.id, report_user_id=test_user.id,
                           good_qty=5, bad_qty=0, remark="", attachment_ids=None)

    create_audit(session, tenant_id=tenant.id, report_id=report.id, auditor_id=test_user.id, audit_level="leader", action="approve", reason=None)
    update_report_status(session, report, "leader_approved")
    salary = calc_and_create_salary(session, tenant_id=tenant.id, report=report)
    session.flush()
    assert salary is not None
    # 5 * 1.50 = 7.50
    assert float(salary.amount) == 7.5
