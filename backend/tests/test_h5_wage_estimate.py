# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""报工即时预估工资：与终审 SalaryItem 口径一致。"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.product import Product
from app.models.sku import Sku
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.services.wage_estimate import estimate_wage


def _task(db: Session, customer: Customer, product: Product, sku: Sku, process: Process) -> Task:
    order = Order(customer_id=customer.id, code="SO-WAGE-1", status="confirmed")
    order.items = [OrderItem(line_no=1, sku_id=sku.id, qty=10, unit_price=Decimal("9"), subtotal=Decimal("90"))]
    db.add(order)
    db.flush()
    wo = WorkOrder(
        order_id=order.id,
        order_item_id=order.items[0].id,
        product_id=product.id,
        sku_id=sku.id,
        qty=10,
    )
    db.add(wo)
    db.flush()
    task = Task(work_order_id=wo.id, process_id=process.id, seq=1, task_code="T-WAGE-1", planned_qty=10)
    db.add(task)
    db.flush()
    return task


def test_estimate_matches_process_price(session: Session, customer: Customer, product: Product, sku: Sku, process: Process):
    task = _task(session, customer, product, sku, process)
    session.add(ProcessPrice(sku_id=sku.id, process_id=process.id, unit_price=Decimal("2.5000"), is_active=True))
    session.flush()

    est = estimate_wage(session, task, 6)
    assert est["priced"] is True
    assert est["unit_price"] == 2.5
    assert est["amount"] == 15.0


def test_estimate_unpriced(session: Session, customer: Customer, product: Product, sku: Sku, process: Process):
    task = _task(session, customer, product, sku, process)
    est = estimate_wage(session, task, 6)
    assert est == {"unit_price": 0.0, "amount": 0.0, "priced": False}


def test_estimate_zero_qty(session: Session, customer: Customer, product: Product, sku: Sku, process: Process):
    task = _task(session, customer, product, sku, process)
    session.add(ProcessPrice(sku_id=sku.id, process_id=process.id, unit_price=Decimal("2.5"), is_active=True))
    session.flush()
    assert estimate_wage(session, task, 0)["priced"] is False
