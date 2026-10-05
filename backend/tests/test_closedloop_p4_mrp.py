# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""第四批·4：MRP 净需求口径 + 建议量落成采购草稿单。

覆盖三件以前没有的事：在途量参与扣减、库存按仓库口径取、建议行能追溯到采购单。
"""
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.mrp import compute_mrp, convert_plan_to_purchase_orders
from app.crud.purchase_order import confirm_purchase_order, create_purchase_order
from app.models.approval_record import ApprovalRecord
from app.models.material import Material, MaterialBom, MaterialBomItem, Supplier
from app.models.mrp import MrpItem, MrpPlan
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.purchase import PurchaseOrder
from app.models.sku import Sku
from app.models.user import User
from app.models.warehouse import Stock, Warehouse
from app.models.work_order import WorkOrder


# ────────────────────────── 构造工具 ──────────────────────────


@pytest.fixture
def warehouse(session: Session) -> Warehouse:
    return _warehouse(session, "WH-MAIN")


def _sku(session: Session, product: Product, code: str) -> Sku:
    s = Sku(product_id=product.id, code=code, name=f"型号{code}", is_active=True)
    session.add(s)
    session.flush()
    return s


def _supplier(session: Session, code: str) -> Supplier:
    s = Supplier(code=code, name=f"供应商{code}", is_active=True)
    session.add(s)
    session.flush()
    return s


def _material(session: Session, product: Product, code: str, supplier_id: int | None = None) -> Material:
    m = Material(
        code=code,
        name=f"物料{code}",
        unit="个",
        sku_id=_sku(session, product, f"KS-{code}").id,
        supplier_id=supplier_id,
        is_active=True,
    )
    session.add(m)
    session.flush()
    return m


def _bom(session: Session, sku_id: int, lines: list[tuple[Material, int]]) -> MaterialBom:
    bom = MaterialBom(scope="sku", sku_id=sku_id, name="测试BOM", is_default=True, is_active=True)
    session.add(bom)
    session.flush()
    for material, qty_per in lines:
        session.add(MaterialBomItem(bom_id=bom.id, material_id=material.id, qty_per=qty_per))
    session.flush()
    session.expire_all()
    return bom


def _warehouse(session: Session, code: str, is_active: bool = True) -> Warehouse:
    w = Warehouse(code=code, name=f"仓库{code}", is_active=is_active)
    session.add(w)
    session.flush()
    return w


def _stock(session: Session, warehouse: Warehouse, sku: Sku, qty: int) -> Stock:
    s = Stock(warehouse_id=warehouse.id, sku_id=sku.id, qty=qty)
    session.add(s)
    session.flush()
    return s


def _work_order(session: Session, customer, sku: Sku, qty: int, tag: str) -> WorkOrder:
    order = Order(customer_id=customer.id, code=f"SO-MRP-{tag}", status="confirmed", amount=0, cost_amount=0)
    session.add(order)
    session.flush()
    item = OrderItem(order_id=order.id, line_no=1, sku_id=sku.id, qty=qty, unit_price=1.5, subtotal=1.5 * qty)
    session.add(item)
    session.flush()
    wo = WorkOrder(
        order_id=order.id, order_item_id=item.id, product_id=sku.product_id,
        sku_id=sku.id, qty=qty, status="open",
    )
    session.add(wo)
    session.flush()
    return wo


def _row(plan: MrpPlan, material_id: int) -> MrpItem:
    for item in plan.items:
        if item.material_id == material_id:
            return item
    raise AssertionError(f"计划 {plan.code} 里没有物料 {material_id} 的建议行")


# ────────────────────────── 1. 净需求口径 ──────────────────────────


def test_net_requirement_credits_stock_and_on_order(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    """净需求 = 毛需求 −（库存 + 在途）。在途以前完全没参与。"""
    mat = _material(session, product, "M001")
    _bom(session, sku.id, [(mat, 2)])
    _stock(session, warehouse, session.get(Sku, mat.sku_id), 50)
    wo = _work_order(session, customer, sku, 100, "A")

    po = create_purchase_order(
        session, supplier_id=_supplier(session, "S001").id, code=None, remark="在途", created_by=test_user.id,
        items=[(mat.id, 30, None, None)],
    )
    confirm_purchase_order(session, po, test_user.id)

    plan = compute_mrp(session, [wo.id], test_user.id, None)
    item = _row(plan, mat.id)
    assert item.gross_qty == 200
    assert item.stock_qty == 50
    assert item.on_order_qty == 30
    assert item.net_qty == 120
    assert item.suggested_purchase_qty == 120
    assert plan.total_purchase_qty == 120


def test_draft_purchase_order_does_not_count_as_on_order(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    """草稿单还没下出去，占不了需求。"""
    mat = _material(session, product, "M002")
    _bom(session, sku.id, [(mat, 1)])
    wo = _work_order(session, customer, sku, 100, "B")
    create_purchase_order(
        session, supplier_id=_supplier(session, "S002").id, code=None, remark="草稿", created_by=test_user.id,
        items=[(mat.id, 40, None, None)],
    )

    item = _row(compute_mrp(session, [wo.id], test_user.id, None), mat.id)
    assert item.on_order_qty == 0
    assert item.net_qty == 100


def test_inactive_warehouse_stock_is_not_available(
    session: Session, test_user: User, product: Product, sku: Sku, customer
):
    closed = _warehouse(session, "WH-OFF", is_active=False)
    mat = _material(session, product, "M003")
    _bom(session, sku.id, [(mat, 1)])
    _stock(session, closed, session.get(Sku, mat.sku_id), 999)
    wo = _work_order(session, customer, sku, 100, "C")

    item = _row(compute_mrp(session, [wo.id], test_user.id, None), mat.id)
    assert item.stock_qty == 0
    assert item.net_qty == 100


def test_explicit_warehouse_scope_overrides_is_active_filter(
    session: Session, test_user: User, product: Product, sku: Sku, customer
):
    """指定仓库时按指定算——车间临时仓停用了也要能查。"""
    closed = _warehouse(session, "WH-TMP", is_active=False)
    mat = _material(session, product, "M004")
    _bom(session, sku.id, [(mat, 1)])
    _stock(session, closed, session.get(Sku, mat.sku_id), 60)
    wo = _work_order(session, customer, sku, 100, "D")

    item = _row(compute_mrp(session, [wo.id], test_user.id, None, [closed.id]), mat.id)
    assert item.stock_qty == 60
    assert item.net_qty == 40


def test_shared_stock_pool_is_consumed_in_order(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    """两张工单共用一种料：库存是一个池子，不是每张工单各看一次全额。"""
    mat = _material(session, product, "M005")
    _bom(session, sku.id, [(mat, 1)])
    _stock(session, warehouse, session.get(Sku, mat.sku_id), 100)
    wo1 = _work_order(session, customer, sku, 60, "E1")
    wo2 = _work_order(session, customer, sku, 60, "E2")

    plan = compute_mrp(session, [wo1.id, wo2.id], test_user.id, None)
    rows = sorted((i.gross_qty, i.net_qty) for i in plan.items)
    assert rows == [(60, 0), (60, 20)]
    assert plan.total_purchase_qty == 20
    assert plan.total_materials == 1


def test_last_purchase_price_is_backfilled(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    mat = _material(session, product, "M006", None)
    _bom(session, sku.id, [(mat, 1)])
    wo = _work_order(session, customer, sku, 10, "F")
    supplier = _supplier(session, "S006")
    create_purchase_order(
        session, supplier_id=supplier.id, code=None, remark="历史价", created_by=test_user.id,
        items=[(mat.id, 5, 3.5, None)],
    )

    item = _row(compute_mrp(session, [wo.id], test_user.id, None), mat.id)
    assert Decimal(str(item.unit_price)) == Decimal("3.50")
    # 物料档案没填供应商时，退回按最近一次采购的供应商建议，否则这行永远转不出去
    assert item.supplier_id == supplier.id


def test_compute_writes_trail_and_rejects_missing_bom(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    mat = _material(session, product, "M007")
    _bom(session, sku.id, [(mat, 1)])
    wo = _work_order(session, customer, sku, 8, "G")

    plan = compute_mrp(session, [wo.id], test_user.id, "周排产")
    row = session.scalars(
        select(ApprovalRecord).where(
            ApprovalRecord.biz_type == "mrp_plan", ApprovalRecord.biz_id == plan.id
        )
    ).one()
    assert row.action == "compute"
    assert row.to_status == "computed"
    assert row.operator_name == "管理员"

    other_sku = _sku(session, product, "SKU-NOBOM")
    lonely = _work_order(session, customer, other_sku, 5, "H")
    with pytest.raises(ValueError, match="BOM"):
        compute_mrp(session, [lonely.id], test_user.id, None)


# ────────────────────────── 2. 转采购落地 ──────────────────────────


def test_convert_groups_by_supplier_and_merges_same_material(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    """同供应商合成一张单、同物料合成一行；落的是草稿单，确认仍由人点。"""
    sup_a = _supplier(session, "SA")
    sup_b = _supplier(session, "SB")
    mat_a = _material(session, product, "M100", sup_a.id)
    mat_b = _material(session, product, "M101", sup_b.id)
    mat_c = _material(session, product, "M102", sup_a.id)
    _bom(session, sku.id, [(mat_a, 1), (mat_b, 1), (mat_c, 1)])
    wo1 = _work_order(session, customer, sku, 50, "I1")
    wo2 = _work_order(session, customer, sku, 30, "I2")

    plan = compute_mrp(session, [wo1.id, wo2.id], test_user.id, None)
    assert plan.total_purchase_qty == 240  # (50+30) * 3

    result = convert_plan_to_purchase_orders(session, plan.id, operator_id=test_user.id)
    assert result["status"] == "converted"
    assert len(result["purchase_orders"]) == 2
    assert {po["lines"] for po in result["purchase_orders"]} == {1, 2}

    orders = session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id)).all()
    assert {o.status for o in orders} == {"draft"}
    by_supplier = {o.supplier_id: o for o in orders}
    assert sum(i.qty for i in by_supplier[sup_a.id].items) == 160  # M100 + M102 各 80
    assert sum(i.qty for i in by_supplier[sup_b.id].items) == 80
    assert len(by_supplier[sup_a.id].items) == 2

    session.refresh(plan)
    stamped = {i.purchase_order_id for i in plan.items}
    assert stamped == {o.id for o in orders}

    trail = session.scalars(
        select(ApprovalRecord).where(
            ApprovalRecord.biz_type == "mrp_plan", ApprovalRecord.biz_id == plan.id
        ).order_by(ApprovalRecord.id)
    ).all()
    assert [t.action for t in trail] == ["compute", "convert"]
    assert trail[1].operator_id == test_user.id


def test_convert_can_select_rows_and_leaves_rest_pending(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    sup = _supplier(session, "SC")
    mat1 = _material(session, product, "M200", sup.id)
    mat2 = _material(session, product, "M201", sup.id)
    _bom(session, sku.id, [(mat1, 1), (mat2, 1)])
    wo = _work_order(session, customer, sku, 20, "J")

    plan = compute_mrp(session, [wo.id], test_user.id, None)
    picked = _row(plan, mat1.id)
    result = convert_plan_to_purchase_orders(session, plan.id, operator_id=test_user.id, item_ids=[picked.id])

    assert result["status"] == "partial_converted"
    assert result["converted_items"] == 1
    session.refresh(plan)
    assert picked.purchase_order_id is not None
    assert _row(plan, mat2.id).purchase_order_id is None

    # 同一行不能转两次
    with pytest.raises(ValueError, match="没有可转采购"):
        convert_plan_to_purchase_orders(session, plan.id, operator_id=test_user.id, item_ids=[picked.id])


def test_convert_without_supplier_is_skipped_not_fabricated(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    sup = _supplier(session, "SD")
    with_sup = _material(session, product, "M300", sup.id)
    no_sup = _material(session, product, "M301", None)
    _bom(session, sku.id, [(with_sup, 1), (no_sup, 1)])
    wo = _work_order(session, customer, sku, 15, "K")

    plan = compute_mrp(session, [wo.id], test_user.id, None)
    result = convert_plan_to_purchase_orders(session, plan.id, operator_id=test_user.id)

    assert result["skipped_no_supplier"] == 1
    assert result["status"] == "partial_converted"
    assert session.query(PurchaseOrder).count() == 1
    session.refresh(plan)
    assert _row(plan, no_sup.id).purchase_order_id is None


def test_convert_rejects_plan_with_nothing_to_convert(
    session: Session, test_user: User, product: Product, sku: Sku, customer, warehouse: Warehouse
):
    mat = _material(session, product, "M400", _supplier(session, "SE").id)
    _bom(session, sku.id, [(mat, 1)])
    _stock(session, warehouse, session.get(Sku, mat.sku_id), 500)
    wo = _work_order(session, customer, sku, 10, "L")

    plan = compute_mrp(session, [wo.id], test_user.id, None)
    assert plan.total_purchase_qty == 0
    with pytest.raises(ValueError, match="没有可转采购"):
        convert_plan_to_purchase_orders(session, plan.id, operator_id=test_user.id)
    assert session.query(PurchaseOrder).count() == 0


def test_convert_unknown_plan_raises(session: Session, test_user: User):
    with pytest.raises(ValueError, match="不存在"):
        convert_plan_to_purchase_orders(session, 999999, operator_id=test_user.id)
