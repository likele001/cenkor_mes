# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库存过账入口：重复确认/取消必须被状态拦住，只落一次账。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.admin.purchase import orders as purchase_orders_api
from app.api.admin.purchase.orders import receive_api
from app.crud.material_issue import cancel_issue, create_issue, issue_materials
from app.crud.warehouse import adjust_stock, create_warehouse
from app.crud.warehouse_entry import cancel_entry, confirm_entry, create_entry
from app.models.material import Material, Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.warehouse import Stock
from app.schemas.purchase_order import PurchaseOrderReceiveIn


@pytest.fixture
def warehouse(session):
    wh = create_warehouse(session, code="WH-1", name="一号仓")
    session.flush()
    return wh


@pytest.fixture
def material(session, sku):
    supplier = Supplier(code="SUP-1", name="测试供应商")
    session.add(supplier)
    session.flush()
    m = Material(code="MAT-1", name="面料", sku_id=sku.id, supplier_id=supplier.id, is_active=True)
    session.add(m)
    session.flush()
    return m


def _qty(session, warehouse_id: int, sku_id: int) -> int:
    value = session.scalar(
        select(Stock.qty).where(Stock.warehouse_id == warehouse_id, Stock.sku_id == sku_id)
    )
    return int(value or 0)


# ── 领料 ─────────────────────────────────────────────────────────────


def test_issue_second_time_is_rejected(session, warehouse, material, sku, test_user):
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=10, biz_type="other")
    issue = create_issue(
        session, code="LI-1", warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": 4}],
    )
    session.flush()

    issue_materials(session, issue, issued_by=test_user.id)

    with pytest.raises(ValueError, match="状态不允许领料"):
        issue_materials(session, issue, issued_by=test_user.id)

    session.refresh(issue)
    assert issue.status == "issued"
    assert _qty(session, warehouse.id, sku.id) == 6


def test_issued_issue_cannot_be_cancelled(session, warehouse, material, sku):
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=10, biz_type="other")
    issue = create_issue(
        session, code="LI-2", warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": 3}],
    )
    session.flush()
    issue_materials(session, issue)

    with pytest.raises(ValueError, match="状态不允许取消"):
        cancel_issue(session, issue)
    assert _qty(session, warehouse.id, sku.id) == 7


def test_missing_issue_is_rejected(session):
    from app.models.material_issue import MaterialIssue

    ghost = MaterialIssue(code="LI-X", warehouse_id=1, status="draft")
    ghost.id = 999999
    with pytest.raises(ValueError, match="领料单不存在"):
        issue_materials(session, ghost)


# ── 入库 ─────────────────────────────────────────────────────────────


def test_entry_cannot_be_confirmed_twice(session, warehouse, material, sku):
    entry = create_entry(
        session, code="WE-1", source_type="other", warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": 5}],
    )
    session.flush()

    confirm_entry(session, entry)
    with pytest.raises(ValueError, match="状态不允许确认"):
        confirm_entry(session, entry)

    session.refresh(entry)
    assert entry.status == "confirmed"
    assert _qty(session, warehouse.id, sku.id) == 5


def test_confirmed_entry_cannot_be_cancelled(session, warehouse, material, sku):
    entry = create_entry(
        session, code="WE-2", source_type="other", warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": 2}],
    )
    session.flush()
    confirm_entry(session, entry)

    with pytest.raises(ValueError, match="状态不允许取消"):
        cancel_entry(session, entry)
    assert _qty(session, warehouse.id, sku.id) == 2


def test_missing_entry_is_rejected(session):
    from app.models.warehouse_entry import WarehouseEntry

    ghost = WarehouseEntry(code="WE-X", warehouse_id=1, status="draft")
    ghost.id = 999999
    with pytest.raises(ValueError, match="入库单不存在"):
        confirm_entry(session, ghost)


# ── 采购收货 ─────────────────────────────────────────────────────────


@pytest.fixture
def purchase_order(session, material):
    po = PurchaseOrder(code="PO-1", supplier_id=material.supplier_id, status="confirmed")
    po.items = [PurchaseOrderItem(material_id=material.id, qty=20)]
    session.add(po)
    session.flush()
    return po


def _request():
    return SimpleNamespace(
        client=None,
        headers={},
        method="POST",
        url=SimpleNamespace(path="/api/admin/purchase/orders/1/receive"),
    )


def test_receive_twice_only_books_once(session, warehouse, material, sku, purchase_order, test_user, monkeypatch):
    # operation_logs 在 SQLite 下 BigInteger 主键不自增，这里只验证收货本身
    monkeypatch.setattr(purchase_orders_api, "write_op_log", lambda *a, **kw: None)
    payload = PurchaseOrderReceiveIn(warehouse_id=warehouse.id, items=None)

    receive_api(purchase_order.id, payload, _request(), db=session, user=test_user)
    session.refresh(purchase_order)
    assert purchase_order.status == "received"
    assert _qty(session, warehouse.id, sku.id) == 20

    with pytest.raises(HTTPException) as exc:
        receive_api(purchase_order.id, payload, _request(), db=session, user=test_user)
    assert exc.value.status_code == 400
    assert _qty(session, warehouse.id, sku.id) == 20


def test_receive_missing_order_returns_404(session, warehouse, test_user):
    with pytest.raises(HTTPException) as exc:
        receive_api(999999, PurchaseOrderReceiveIn(warehouse_id=warehouse.id),
                    _request(), db=session, user=test_user)
    assert exc.value.status_code == 404
