# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库存盘点：制单快照 / 录实盘 / 确认入账

盘点最容易做错的两件事，这里各钉一个用例：

1. **确认时必须按「实盘 − 当前账面」入账**，不是「实盘 − 快照账面」。
   制单到确认之间仓库还在收发，用快照差额回冲会把这段真实业务抹掉
   （见 test_confirm_uses_live_balance_not_snapshot）。
2. **入账必须走 adjust_stock 留下 stocktake 流水**，不能直改 stocks.qty，
   否则库存流水断链、事后查不出差异去哪了（见 test_confirm_writes_stocktake_log）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.stocktake import (
    StocktakeStateError,
    add_item,
    cancel_stocktake,
    confirm_stocktake,
    create_stocktake,
    get_stocktake,
    record_counts,
    remove_item,
)
from app.crud.warehouse import adjust_stock, create_warehouse
from app.models.permission import Permission
from app.models.role import role_permissions
from app.models.sku import Sku
from app.models.stocktake import Stocktake
from app.models.warehouse import Stock, StockLog, Warehouse


@pytest.fixture(scope="session")
def engine():
    """HTTP 用例要跨线程复用同一条 SQLite 连接，所以这里换成 StaticPool。"""
    from app.models.base import Base

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

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
    session.flush()
    return wh


@pytest.fixture
def second_sku(product, session: Session) -> Sku:
    s = Sku(product_id=product.id, code="SKU002", name="测试型号B", is_active=True)
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def stocked(session: Session, warehouse: Warehouse, sku: Sku, second_sku: Sku) -> dict:
    """账上：A 有 50，B 有 0（只是被碰过的行）。"""
    session.add(Stock(warehouse_id=warehouse.id, sku_id=sku.id, qty=50))
    session.add(Stock(warehouse_id=warehouse.id, sku_id=second_sku.id, qty=0))
    session.flush()
    return {"a": sku, "b": second_sku}


def _qty(session: Session, warehouse_id: int, sku_id: int) -> int:
    return int(session.scalar(
        select(Stock.qty).where(Stock.warehouse_id == warehouse_id, Stock.sku_id == sku_id)
    ) or 0)


def _logs(session: Session, sku_id: int) -> list[StockLog]:
    return list(session.scalars(
        select(StockLog).where(StockLog.sku_id == sku_id).order_by(StockLog.id)
    ))


def _item(st, sku_id: int):
    return next(it for it in st.items if it.sku_id == sku_id)


# ────────────────────────── 1. 制单快照 ──────────────────────────

def test_create_snapshots_book_qty(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD1", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)

    assert st.status == "draft"
    assert st.scope == "all"
    assert st.total_items == 2
    assert _item(st, stocked["a"].id).book_qty == 50
    assert _item(st, stocked["b"].id).book_qty == 0, "账上为 0 但存在的行也要进盘点表，否则永远发现不了盘盈"
    assert _item(st, stocked["a"].id).counted_qty is None


def test_create_only_selected_skus(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD2", warehouse_id=warehouse.id, sku_ids=[stocked["b"].id])
    session.flush()
    st = get_stocktake(session, st.id)

    assert st.scope == "selected"
    assert [it.sku_id for it in st.items] == [stocked["b"].id]


def test_create_selected_sku_without_stock_row_gets_zero(session: Session, warehouse: Warehouse, product):
    """指定型号但账上根本没有库存行 → book_qty=0，实盘录了就是盘盈。"""
    orphan = Sku(product_id=product.id, code="SKU-ORPHAN", name="账外型号", is_active=True)
    session.add(orphan)
    session.flush()

    st = create_stocktake(session, code="PD3", warehouse_id=warehouse.id, sku_ids=[orphan.id])
    session.flush()
    st = get_stocktake(session, st.id)
    assert st.total_items == 1 and _item(st, orphan.id).book_qty == 0


def test_create_rejects_empty_scope(session: Session, warehouse: Warehouse):
    with pytest.raises(ValueError) as exc:
        create_stocktake(session, code="PD4", warehouse_id=warehouse.id)
    assert "没有库存行可盘" in str(exc.value)


def test_create_rejects_unknown_sku(session: Session, warehouse: Warehouse):
    with pytest.raises(ValueError):
        create_stocktake(session, code="PD5", warehouse_id=warehouse.id, sku_ids=[99999])


# ────────────────────────── 2. 录实盘 ──────────────────────────

def test_record_counts_sets_diff_and_status(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD6", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    a_item = _item(st, stocked["a"].id)

    record_counts(session, st, [{"item_id": a_item.id, "counted_qty": 47}])
    session.flush()
    st = get_stocktake(session, st.id)

    assert st.status == "counting", "录了实盘数就该进盘点中，不能再当草稿随意删行"
    assert st.counted_items == 1
    assert st.diff_items == 1
    assert _item(st, stocked["a"].id).diff_qty == -3


def test_record_counts_rejects_negative(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD7", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    with pytest.raises(ValueError):
        record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": -1}])


def test_record_counts_rejects_foreign_item(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD8", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    with pytest.raises(ValueError):
        record_counts(session, st, [{"item_id": 99999, "counted_qty": 1}])


# ────────────────────────── 3. 确认入账 ──────────────────────────

def test_confirm_requires_at_least_one_counted(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD9", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    with pytest.raises(ValueError) as exc:
        confirm_stocktake(session, st)
    assert "没有任何一行录入实盘数" in str(exc.value)


def test_confirm_writes_stocktake_log(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD10", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 45}])
    session.flush()
    st = get_stocktake(session, st.id)

    result = confirm_stocktake(session, st, confirmed_by=1)
    session.flush()

    assert result["adjusted_lines"] == 1 and result["loss_qty"] == 5 and result["gain_qty"] == 0
    assert _qty(session, warehouse.id, stocked["a"].id) == 45

    logs = _logs(session, stocked["a"].id)
    assert len(logs) == 1
    assert logs[0].biz_type == "stocktake", "盘点必须留 stocktake 流水，否则差异去哪了查不出来"
    assert logs[0].biz_id == st.id
    assert logs[0].change_qty == -5
    assert logs[0].balance_qty == 45

    st = get_stocktake(session, st.id)
    assert st.status == "confirmed"
    assert _item(st, stocked["a"].id).adjusted_qty == -5


def test_confirm_uses_live_balance_not_snapshot(session: Session, warehouse: Warehouse, stocked: dict):
    """制单快照 50 → 期间出库 20（账面 30）→ 实盘 28。

    正确入账是 28 − 30 = −2（只补盘亏 2），库存在 28；
    如果错按快照差额 28 − 50 = −22 入账，那 20 件真实出库会被抹掉，
    账面变成 8，账实彻底对不上。
    """
    st = create_stocktake(session, code="PD11", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    assert _item(st, stocked["a"].id).book_qty == 50

    adjust_stock(session, warehouse_id=warehouse.id, sku_id=stocked["a"].id,
                 change_qty=-20, biz_type="ship_out")
    session.flush()

    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 28}])
    session.flush()
    st = get_stocktake(session, st.id)
    confirm_stocktake(session, st)
    session.flush()

    assert _qty(session, warehouse.id, stocked["a"].id) == 28, "确认后账面必须等于实盘数"
    st = get_stocktake(session, st.id)
    it = _item(st, stocked["a"].id)
    assert it.diff_qty == -22, "管理口径的账实差异仍按快照账面对比"
    assert it.adjusted_qty == -2, "入账变动按确认时的当前账面算，不能抹掉期间真实出库"


def test_confirm_gain_creates_stock_row(session: Session, warehouse: Warehouse, product):
    """账外物资：账上没有库存行，实盘 3 件 → 建行并记盘盈。"""
    orphan = Sku(product_id=product.id, code="SKU-GAIN", name="盘盈型号", is_active=True)
    session.add(orphan)
    session.flush()

    st = create_stocktake(session, code="PD12", warehouse_id=warehouse.id, sku_ids=[orphan.id])
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, orphan.id).id, "counted_qty": 3}])
    session.flush()
    st = get_stocktake(session, st.id)
    result = confirm_stocktake(session, st)
    session.flush()

    assert result["gain_qty"] == 3
    assert _qty(session, warehouse.id, orphan.id) == 3
    logs = _logs(session, orphan.id)
    assert [l.change_qty for l in logs] == [3]


def test_confirm_without_diff_leaves_no_log(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD13", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 50}])
    session.flush()
    st = get_stocktake(session, st.id)
    result = confirm_stocktake(session, st)
    session.flush()

    assert result["adjusted_lines"] == 0
    assert _logs(session, stocked["a"].id) == [], "账实相符不该造一条 0 变动流水"
    assert _qty(session, warehouse.id, stocked["a"].id) == 50


def test_uncounted_rows_are_left_alone(session: Session, warehouse: Warehouse, stocked: dict):
    """只盘了一行就确认：没盘的行不能被动，否则等于把没点的货清零。"""
    adjust_stock(session, warehouse_id=warehouse.id, sku_id=stocked["b"].id, change_qty=9, biz_type="produce_in")
    session.flush()

    st = create_stocktake(session, code="PD14", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 50}])
    session.flush()
    st = get_stocktake(session, st.id)
    confirm_stocktake(session, st)
    session.flush()

    assert _qty(session, warehouse.id, stocked["b"].id) == 9


# ────────────────────────── 4. 状态机 ──────────────────────────

def test_confirmed_is_terminal(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD15", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 50}])
    session.flush()
    st = get_stocktake(session, st.id)
    confirm_stocktake(session, st)
    session.flush()
    st = get_stocktake(session, st.id)

    with pytest.raises(StocktakeStateError):
        cancel_stocktake(session, st)
    with pytest.raises(StocktakeStateError):
        confirm_stocktake(session, st)
    with pytest.raises(StocktakeStateError):
        record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 1}])


def test_cancel_keeps_stock_untouched(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD16", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 1}])
    session.flush()
    st = get_stocktake(session, st.id)
    cancel_stocktake(session, st)
    session.flush()

    assert st.status == "cancelled"
    assert _qty(session, warehouse.id, stocked["a"].id) == 50


def test_add_and_remove_item(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD17", warehouse_id=warehouse.id, sku_ids=[stocked["a"].id])
    session.flush()
    st = get_stocktake(session, st.id)
    assert st.total_items == 1

    add_item(session, st, stocked["b"].id)
    session.flush()
    st = get_stocktake(session, st.id)
    assert st.total_items == 2

    with pytest.raises(ValueError):
        add_item(session, st, stocked["b"].id)

    remove_item(session, st, _item(st, stocked["b"].id).id)
    session.flush()
    st = get_stocktake(session, st.id)
    assert st.total_items == 1


def test_remove_counted_item_rejected(session: Session, warehouse: Warehouse, stocked: dict):
    st = create_stocktake(session, code="PD18", warehouse_id=warehouse.id)
    session.flush()
    st = get_stocktake(session, st.id)
    record_counts(session, st, [{"item_id": _item(st, stocked["a"].id).id, "counted_qty": 47}])
    session.flush()
    st = get_stocktake(session, st.id)
    with pytest.raises(ValueError):
        remove_item(session, st, _item(st, stocked["a"].id).id)


# ────────────────────────── 5. HTTP 装配层 ──────────────────────────

def test_api_flow_end_to_end(api, session: Session, admin_role, test_user, warehouse, stocked: dict):
    """走真实 HTTP（含 RBAC 与响应包装），把制单→录实盘→确认跑一遍。"""
    _grant(session, admin_role, ["warehouse.view", "warehouse.manage"])
    headers = _auth(test_user)

    r = api.post("/api/admin/warehouse/stocktakes",
                 json={"warehouse_id": warehouse.id, "remark": "盘点冒烟"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    st_id = body["id"]
    assert body["code"].startswith("PD"), "单号必须走 PD 前缀自动生成"
    assert body["total_items"] == 2

    item_id = next(it["id"] for it in body["items"] if it["sku_id"] == stocked["a"].id)
    r = api.put(f"/api/admin/warehouse/stocktakes/{st_id}/items",
                json={"items": [{"item_id": item_id, "counted_qty": 48}]}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "counting"

    r = api.post(f"/api/admin/warehouse/stocktakes/{st_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["loss_qty"] == 2
    assert data["stocktake"]["status"] == "confirmed"

    r = api.get(f"/api/admin/warehouse/stocktakes/{st_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["items"], "详情必须带明细"


def test_api_write_requires_manage_permission(api, session: Session, admin_role, test_user, warehouse):
    """只有 warehouse.view 的人能看盘单，不能制单。

    注意：本项目的响应包装把 HTTP 状态一律回 200，业务码在 body 的 `code` 里，
    所以这里断言的是 body["code"] 而不是 status_code。
    """
    _grant(session, admin_role, ["warehouse.view"])
    headers = _auth(test_user)
    r = api.post("/api/admin/warehouse/stocktakes",
                 json={"warehouse_id": warehouse.id}, headers=headers)
    assert r.json()["code"] == 403, r.text


def test_api_error_mapping(api, session: Session, admin_role, test_user, warehouse):
    """404 与 400 要分得清，前端才知道是该刷新列表还是该改输入。"""
    _grant(session, admin_role, ["warehouse.view", "warehouse.manage"])
    headers = _auth(test_user)

    assert api.get("/api/admin/warehouse/stocktakes/99999", headers=headers).json()["code"] == 404

    r = api.post("/api/admin/warehouse/stocktakes", json={"warehouse_id": warehouse.id}, headers=headers)
    assert r.json()["code"] == 400
    assert "没有库存行可盘" in r.json()["msg"]


def test_api_create_never_returns_server_error(api, session: Session, admin_role, test_user, warehouse, stocked: dict):
    """空 body 也不许 500/501：这条钉住 API 与 crud 的参数装配不脱节。"""
    _grant(session, admin_role, ["warehouse.view", "warehouse.manage"])
    headers = _auth(test_user)
    r = api.post("/api/admin/warehouse/stocktakes", json={}, headers=headers)
    assert r.status_code not in (500, 501), r.text


def test_list_counts_and_filters(api, session: Session, admin_role, test_user, warehouse, stocked: dict):
    _grant(session, admin_role, ["warehouse.view", "warehouse.manage"])
    headers = _auth(test_user)
    api.post("/api/admin/warehouse/stocktakes", json={"warehouse_id": warehouse.id}, headers=headers)

    r = api.get("/api/admin/warehouse/stocktakes", params={"warehouse_id": warehouse.id}, headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 1 and data["items"]
    assert "items" not in data["items"][0], "列表页不该把明细全捞出来"

    r = api.get("/api/admin/warehouse/stocktakes", params={"status": "confirmed"}, headers=headers)
    assert all(x["status"] == "confirmed" for x in r.json()["data"]["items"])
