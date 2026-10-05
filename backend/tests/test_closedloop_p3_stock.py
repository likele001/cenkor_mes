# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""闭环体检第三批：账实一致

库存是所有出入库的唯一落账口，以前既不校验负数也不认仓库；发货单、委外收发、
采购入库各自为政，同一批货能被入两遍。这里锁住扣减下限、仓库归属与统一入库口。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.subcontract import add_receive_log, add_send_log, create_order as create_subcontract_order
from app.crud.warehouse import StockShortage, adjust_stock, create_warehouse, resolve_warehouse_id
from app.crud.warehouse_entry import cancel_entry, confirm_entry, create_entry
from app.models.material import Material, Supplier
from app.models.permission import Permission
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.role import role_permissions
from app.models.sku import Sku
from app.models.warehouse import Stock, StockLog, Warehouse


@pytest.fixture(scope="session")
def engine():
    """HTTP 用例需要 TestClient 跨线程复用同一条 SQLite 连接（与核心闭环集成测试同一套法）。"""
    from app.models.base import Base

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def api(session):
    from app.main import app

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _grant(session: Session, role, codes: list[str]) -> None:
    for code in codes:
        p = session.scalar(select(Permission).where(Permission.code == code))
        if not p:
            p = Permission(code=code, name=code)
            session.add(p)
            session.flush()
        session.execute(role_permissions.insert().values(role_id=role.id, permission_id=p.id))
    session.flush()


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def warehouse(session: Session) -> Warehouse:
    wh = create_warehouse(session, code="WH-1", name="一号仓")
    session.commit()
    return wh


@pytest.fixture
def second_warehouse(session: Session) -> Warehouse:
    wh = create_warehouse(session, code="WH-2", name="二号仓")
    session.commit()
    return wh


@pytest.fixture
def stocked(session: Session, warehouse: Warehouse, sku: Sku) -> Stock:
    """账上有 50 件。"""
    stock = Stock(warehouse_id=warehouse.id, sku_id=sku.id, qty=50)
    session.add(stock)
    session.commit()
    return stock


def _stock_qty(session: Session, warehouse_id: int, sku_id: int) -> int:
    return int(session.scalar(
        select(Stock.qty).where(Stock.warehouse_id == warehouse_id, Stock.sku_id == sku_id)
    ) or 0)


def _logs(session: Session, sku_id: int) -> list[StockLog]:
    return list(session.scalars(select(StockLog).where(StockLog.sku_id == sku_id).order_by(StockLog.id)))


# ────────────────────────── 1. 扣减下限与流水 ──────────────────────────

def test_outbound_cannot_go_negative(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock):
    with pytest.raises(StockShortage):
        adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=-51, biz_type="ship_out")
    assert _stock_qty(session, warehouse.id, sku.id) == 50, "库存不足必须整笔失败，不能留下一条负数账"


def test_shortage_message_names_the_stock(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock):
    with pytest.raises(StockShortage) as exc:
        adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=-80, biz_type="ship_out")
    text = str(exc.value)
    assert warehouse.name in text and sku.name in text and "缺 30" in text


def test_ledger_balance_tracks_running_total(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock):
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=-20, biz_type="ship_out", biz_id=7)
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=5, biz_type="produce_in")
    session.commit()

    rows = _logs(session, sku.id)
    assert [r.change_qty for r in rows] == [-20, 5]
    assert [r.balance_qty for r in rows] == [30, 35], "流水余额必须逐笔接得上，否则盘点无从对账"
    assert rows[0].biz_id == 7 and rows[0].biz_type == "ship_out"
    assert _stock_qty(session, warehouse.id, sku.id) == 35


def test_zero_and_missing_warehouse_rejected(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock):
    with pytest.raises(ValueError):
        adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=0, biz_type="other")
    with pytest.raises(ValueError):
        adjust_stock(session, warehouse_id=None, sku_id=sku.id, change_qty=1, biz_type="other")


def test_stock_row_created_on_first_movement(session: Session, warehouse: Warehouse, sku: Sku):
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=12, biz_type="purchase_in")
    session.commit()
    assert _stock_qty(session, warehouse.id, sku.id) == 12


# ────────────────────────── 2. 仓库归属 ──────────────────────────

def test_single_active_warehouse_is_implied(session: Session, warehouse: Warehouse):
    assert resolve_warehouse_id(session, None, action="发货") == warehouse.id


def test_multiple_warehouses_must_be_chosen(session: Session, warehouse: Warehouse, second_warehouse: Warehouse):
    with pytest.raises(ValueError) as exc:
        resolve_warehouse_id(session, None, action="发货")
    assert "2 个启用仓库" in str(exc.value)
    assert resolve_warehouse_id(session, second_warehouse.id, action="发货") == second_warehouse.id


def test_inactive_warehouse_is_not_an_option(session: Session, warehouse: Warehouse):
    warehouse.is_active = False
    session.commit()
    with pytest.raises(ValueError):
        resolve_warehouse_id(session, None, action="发货")
    with pytest.raises(ValueError):
        resolve_warehouse_id(session, warehouse.id, action="发货")


# ────────────────────────── 3. 委外收发落库存 ──────────────────────────

@pytest.fixture
def subcontract_order(session: Session, supplier: Supplier, sku: Sku):
    order = create_subcontract_order(
        session,
        supplier_id=supplier.id,
        code="SUB-1",
        remark=None,
        items=[{"sku_id": sku.id, "process_id": None, "qty": 30, "unit_price": None, "remark": None}],
        created_by=None,
    )
    session.commit()
    from app.crud.subcontract import get_order_by_id

    return get_order_by_id(session, order.id)


@pytest.fixture
def supplier(session: Session) -> Supplier:
    s = Supplier(code="SUP-1", name="外协厂")
    session.add(s)
    session.commit()
    return s


def test_subcontract_send_and_receive_moves_stock(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock, subcontract_order):
    item = subcontract_order.items[0]
    add_send_log(session, subcontract_order, item.id, 10, "首批发料", None, warehouse.id)
    session.commit()
    assert _stock_qty(session, warehouse.id, sku.id) == 40
    assert subcontract_order.send_logs[-1].warehouse_id == warehouse.id

    add_receive_log(session, subcontract_order, item.id, 10, "首批收货", None, warehouse.id)
    session.commit()
    assert _stock_qty(session, warehouse.id, sku.id) == 50
    assert [l.biz_type for l in _logs(session, sku.id)] == ["subcontract_out", "subcontract_in"]


def test_subcontract_cannot_send_more_than_ordered(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock, subcontract_order):
    item = subcontract_order.items[0]
    with pytest.raises(ValueError):
        add_send_log(session, subcontract_order, item.id, 31, None, None, warehouse.id)
    assert _stock_qty(session, warehouse.id, sku.id) == 50


def test_subcontract_cannot_receive_more_than_sent(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock, subcontract_order):
    item = subcontract_order.items[0]
    add_send_log(session, subcontract_order, item.id, 10, None, None, warehouse.id)
    session.commit()
    with pytest.raises(ValueError):
        add_receive_log(session, subcontract_order, item.id, 11, None, None, warehouse.id)
    assert _stock_qty(session, warehouse.id, sku.id) == 40


def test_subcontract_send_respects_stock_floor(session: Session, warehouse: Warehouse, sku: Sku, stocked: Stock, subcontract_order):
    item = subcontract_order.items[0]
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=sku.id, change_qty=-45, biz_type="ship_out")
    session.commit()
    with pytest.raises(StockShortage):
        add_send_log(session, subcontract_order, item.id, 30, None, None, warehouse.id)
    assert _stock_qty(session, warehouse.id, sku.id) == 5, "发料失败不能已经扣了账又留下发料记录"
    assert not [l for l in _logs(session, sku.id) if l.biz_type == "subcontract_out"]


# ────────────────────────── 4. 采购入库统一入库口 ──────────────────────────

@pytest.fixture
def material(session: Session, supplier: Supplier, sku: Sku) -> Material:
    m = Material(code="MAT-1", name="面料", sku_id=sku.id, supplier_id=supplier.id, is_active=True)
    session.add(m)
    session.commit()
    return m


@pytest.fixture
def purchase_order(session: Session, supplier: Supplier, material: Material) -> PurchaseOrder:
    po = PurchaseOrder(code="PO-1", supplier_id=supplier.id, status="confirmed")
    po.items = [PurchaseOrderItem(material_id=material.id, qty=40)]
    session.add(po)
    session.commit()
    return po


def _make_entry(session: Session, warehouse: Warehouse, po: PurchaseOrder, sku: Sku, qty: int, code: str = "WE-1"):
    material = po.items[0].material
    entry = create_entry(
        session,
        code=code,
        source_type="purchase",
        warehouse_id=warehouse.id,
        items=[{"material_id": material.id, "sku_id": sku.id, "qty": qty}],
        purchase_order_id=po.id,
    )
    session.commit()
    return entry


def test_entry_confirm_posts_stock_and_marks_po_received(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    entry = _make_entry(session, warehouse, purchase_order, sku, 40)
    confirm_entry(session, entry)
    session.commit()

    assert _stock_qty(session, warehouse.id, sku.id) == 40
    assert purchase_order.items[0].received_qty == 40
    assert purchase_order.status == "received"


def test_partial_entry_keeps_po_open(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    entry = _make_entry(session, warehouse, purchase_order, sku, 15)
    confirm_entry(session, entry)
    session.commit()
    assert purchase_order.items[0].received_qty == 15
    assert purchase_order.status == "partial_received"


def test_over_receipt_is_rejected_at_create(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    with pytest.raises(ValueError):
        _make_entry(session, warehouse, purchase_order, sku, 41)


def test_two_entries_cannot_double_book_the_same_goods(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    """采购页已经收过 40 件，再开一张入库单收同一批货必须被拦下。"""
    first = _make_entry(session, warehouse, purchase_order, sku, 40)
    confirm_entry(session, first)
    session.commit()

    material = purchase_order.items[0].material
    with pytest.raises(ValueError):
        create_entry(
            session,
            code="WE-2",
            source_type="purchase",
            warehouse_id=warehouse.id,
            items=[{"material_id": material.id, "sku_id": sku.id, "qty": 10}],
            purchase_order_id=purchase_order.id,
        )
    assert _stock_qty(session, warehouse.id, sku.id) == 40


def test_confirm_revalidates_when_po_shrank_elsewhere(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    """草稿期够用、确认时已被别的路子占掉——确认必须再拦一次。"""
    entry = _make_entry(session, warehouse, purchase_order, sku, 30)
    purchase_order.items[0].received_qty = 40
    session.commit()
    with pytest.raises(ValueError):
        confirm_entry(session, entry)
    assert _stock_qty(session, warehouse.id, sku.id) == 0


def test_entry_against_draft_po_is_rejected(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    purchase_order.status = "draft"
    session.commit()
    with pytest.raises(ValueError):
        _make_entry(session, warehouse, purchase_order, sku, 5)


def test_return_linked_entry_is_rejected(session: Session, warehouse: Warehouse, sku: Sku):
    material = Material(code="MAT-9", name="余料", sku_id=sku.id, is_active=True)
    session.add(material)
    session.flush()
    with pytest.raises(ValueError):
        create_entry(
            session,
            code="WE-3",
            source_type="other",
            warehouse_id=warehouse.id,
            items=[{"material_id": material.id, "sku_id": sku.id, "qty": 5}],
            material_return_id=1,
        )


def test_cancelled_entry_moves_no_stock(session: Session, warehouse: Warehouse, purchase_order: PurchaseOrder, sku: Sku):
    entry = _make_entry(session, warehouse, purchase_order, sku, 20)
    cancel_entry(session, entry)
    session.commit()
    with pytest.raises(ValueError):
        confirm_entry(session, entry)
    assert _stock_qty(session, warehouse.id, sku.id) == 0
    assert purchase_order.items[0].received_qty == 0


# ────────────────────────── 5. 发货扣库（HTTP 全链路） ──────────────────────────

def _create_shipment(api, headers, order_id: int, warehouse_id: int, sku: Sku, qty: int) -> int:
    resp = api.post(
        "/api/admin/warehouse/shipments",
        headers=headers,
        json={
            "order_id": order_id,
            "code": "SH-1",
            "warehouse_id": warehouse_id,
            "items": [{"sku_id": sku.id, "qty": qty}],
        },
    )
    assert resp.json()["code"] == 200, resp.json()
    return resp.json()["data"]["id"]


def test_ship_deducts_from_the_named_warehouse(
    api, session, admin_role, test_user, warehouse: Warehouse, second_warehouse: Warehouse, sku: Sku, stocked: Stock, order_item
):
    _grant(session, admin_role, ["warehouse.manage", "order.manage"])
    headers = _auth(test_user)
    order, _item = order_item
    adjust_stock(session, warehouse_id=second_warehouse.id, sku_id=sku.id, change_qty=20, biz_type="purchase_in")
    session.commit()

    shipment_id = _create_shipment(api, headers, order.id, second_warehouse.id, sku, 12)
    assert _stock_qty(session, warehouse.id, sku.id) == 50, "建单只是登记，不该已经扣账"

    resp = api.post(f"/api/admin/warehouse/shipments/{shipment_id}/ship", headers=headers)
    assert resp.json()["code"] == 200, resp.json()
    assert _stock_qty(session, second_warehouse.id, sku.id) == 8
    assert _stock_qty(session, warehouse.id, sku.id) == 50, "扣错仓库等于账实两张皮"
    log = _logs(session, sku.id)[-1]
    assert log.biz_type == "ship_out" and log.warehouse_id == second_warehouse.id and log.biz_id == shipment_id


def test_ship_rejected_when_stock_short(
    api, session, admin_role, test_user, warehouse: Warehouse, sku: Sku, stocked: Stock, order_item
):
    _grant(session, admin_role, ["warehouse.manage", "order.manage"])
    headers = _auth(test_user)
    order, _item = order_item

    shipment_id = _create_shipment(api, headers, order.id, warehouse.id, sku, 51)
    resp = api.post(f"/api/admin/warehouse/shipments/{shipment_id}/ship", headers=headers)
    body = resp.json()
    assert body["code"] == 400, body
    assert "库存不足" in str(body["msg"])
    assert _stock_qty(session, warehouse.id, sku.id) == 50


def test_multi_warehouse_shipment_requires_a_warehouse(
    api, session, admin_role, test_user, warehouse: Warehouse, second_warehouse: Warehouse, sku: Sku, order_item
):
    _grant(session, admin_role, ["warehouse.manage", "order.manage"])
    headers = _auth(test_user)
    order, _item = order_item

    resp = api.post(
        "/api/admin/warehouse/shipments",
        headers=headers,
        json={"order_id": order.id, "code": "SH-2", "items": [{"sku_id": sku.id, "qty": 1}]},
    )
    body = resp.json()
    assert body["code"] == 400, body
    assert "必须指定仓库" in str(body["msg"])
