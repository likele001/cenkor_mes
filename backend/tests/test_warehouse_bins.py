# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""仓储库位化服务层回归（migration 0023 引入的 6 张表 + 3 个服务）。

覆盖：入库、可用量、FIFO 出库拆批、按批次调整、移库位、效期预警、正向追溯、
调拨全流程（建单 → 审核 → 执行）。每一步都核对批次账（stock_batch）与汇总账
（stocks）是否同步 —— 这两本账一旦漂移，库位数据就只能看不能用。

为什么用内存库而不是真实库：这个测试的用途是「以后改仓储代码时能立刻知道账
还对不对」，必须能在 CI 里跑。conftest 的 session fixture 是 SQLite 内存库、
每个用例结束整体回滚，这里自建两个仓库 + 一个 SKU，不依赖任何存量数据。

注意必须依赖 conftest 的 tenant fixture：warehouse_location.tenant_id 有外键指向
tenants.id，而 conftest 开了 PRAGMA foreign_keys=ON，没有租户行时插入会撞外键。
这个异常在 ensure_default_location() 里被 `except IntegrityError: pass` 吞掉，
最终只表现为 RuntimeError("默认库位创建失败")，看不出真实原因。
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sku import Sku
from app.models.tenant import Tenant
from app.models.warehouse import Stock, StockBatch, Warehouse, WarehouseLocation
from app.services.warehouse import fifo, trace, transfer


# ── 小工具：直接查两本账，不做任何缓存 ─────────────────────────────────────

def book_qty(db: Session, wh_id: int, sku_id: int) -> int:
    """汇总账（stocks.qty）。没建行视为 0。"""
    v = db.scalar(
        select(Stock.qty).where(Stock.warehouse_id == wh_id, Stock.sku_id == sku_id)
    )
    return int(v or 0)


def batch_qty(db: Session, tenant_id: int, wh_id: int, sku_id: int) -> int:
    """批次账（stock_batch.qty_on_hand 汇总）。"""
    v = db.scalar(
        select(func.coalesce(func.sum(StockBatch.qty_on_hand), 0)).where(
            StockBatch.tenant_id == tenant_id,
            StockBatch.warehouse_id == wh_id,
            StockBatch.sku_id == sku_id,
        )
    )
    return int(v or 0)


def assert_two_books_equal(
    db: Session, tenant_id: int, wh_id: int, sku_id: int, label: str = ""
) -> None:
    """两本账必须相等 —— 抽成断言函数，失败时能直接看出差多少。"""
    b = book_qty(db, wh_id, sku_id)
    c = batch_qty(db, tenant_id, wh_id, sku_id)
    assert b == c, f"{label} 两账不等：汇总 {b} vs 批次 {c}，差 {b - c:+d}"


# ── fixture：两个仓库 + 一个 SKU ────────────────────────────────────────────

def _make_base(db: Session) -> tuple[Warehouse, Warehouse, Sku]:
    prod = Product(code="P-WMS-T", name="仓储回归产品")
    db.add(prod)
    db.flush()

    sku = Sku(product_id=prod.id, code="SKU-WMS-T", name="仓储回归规格")
    db.add(sku)

    src = Warehouse(code="WH-T-SRC", name="回归源仓")
    dst = Warehouse(code="WH-T-DST", name="回归目标仓")
    db.add_all([src, dst])
    db.flush()
    return src, dst, sku


# ── 主流程 ────────────────────────────────────────────────────────────────

def test_receive_auto_location_and_sync_book(session: Session, tenant: Tenant) -> None:
    """入库：自动落 DEFAULT 库位，并把汇总账同步加上去。"""
    tid = tenant.id
    src, _, sku = _make_base(session)

    b1 = fifo.receive(
        session,
        tenant_id=tid,
        warehouse_id=src.id,
        sku_id=sku.id,
        qty=50,
        batch_no="RCV-1",
        biz_type="purchase_in",
        expiry_date=date.today() + timedelta(days=20),
    )
    assert b1.qty_on_hand == 50
    assert b1.location_id is not None, "receive 必须自动落库位，否则唯一键对无库位批次失效"
    assert book_qty(session, src.id, sku.id) == 50
    assert_two_books_equal(session, tid, src.id, sku.id, "入库后")


def test_issue_follows_fifo_and_splits_batches(session: Session, tenant: Tenant) -> None:
    """出库：按效期升序扣减，跨批时拆批，两账保持同步。"""
    tid = tenant.id
    src, _, sku = _make_base(session)

    near = fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=50,
        batch_no="RCV-NEAR", biz_type="purchase_in",
        expiry_date=date.today() + timedelta(days=20),
    )
    fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=40,
        batch_no="RCV-FAR", biz_type="purchase_in",
        expiry_date=date.today() + timedelta(days=200),
    )

    rows = fifo.list_available(session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id)
    assert sum(int(r.get("available") or 0) for r in rows) == 90

    res = fifo.issue(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=60,
        biz_type="ship_out", remark="回归：FIFO 出库",
    )
    alloc = res.get("allocations") or []
    assert len(alloc) >= 2, f"60 大于单批 50，应跨批拆分，实际拆了 {len(alloc)} 批"
    assert alloc[0]["batch_id"] == near.id, "第一个扣的必须是近效期批次"

    session.refresh(near)
    assert near.qty_on_hand == 0, "近效期批次 50 应被扣完"
    assert book_qty(session, src.id, sku.id) == 30
    assert_two_books_equal(session, tid, src.id, sku.id, "出库后")


def test_adjust_hits_exact_batch(session: Session, tenant: Tenant) -> None:
    """按批次调整：只动目标批次，汇总账跟着走。"""
    tid = tenant.id
    src, _, sku = _make_base(session)
    b = fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=40,
        batch_no="ADJ-1", biz_type="purchase_in",
    )
    fifo.adjust(session, tenant_id=tid, batch_id=b.id, qty_delta=-5, reason="回归：盘亏")
    session.refresh(b)
    assert b.qty_on_hand == 35
    assert book_qty(session, src.id, sku.id) == 35
    assert_two_books_equal(session, tid, src.id, sku.id, "调整后")


def test_move_changes_location_not_qty(session: Session, tenant: Tenant) -> None:
    """移库位：换的是 location_id，总量一分不动。"""
    tid = tenant.id
    src, _, sku = _make_base(session)
    b = fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=30,
        batch_no="MOV-1", biz_type="purchase_in",
    )
    target = WarehouseLocation(
        tenant_id=tid, warehouse_id=src.id, code="T-LOC", name="回归库位",
        location_type="bin", is_active=True,
    )
    session.add(target)
    session.flush()

    before = b.qty_on_hand
    moved = fifo.move(session, tenant_id=tid, batch_id=b.id, to_location_id=target.id)
    assert moved.location_id == target.id
    assert moved.qty_on_hand == before, "移库位不该改变在库数量"
    assert_two_books_equal(session, tid, src.id, sku.id, "移库后")


def test_expiry_alerts_structure(session: Session, tenant: Tenant) -> None:
    """效期预警：近效期批次要能出现在 90 天分档里。"""
    tid = tenant.id
    src, _, sku = _make_base(session)
    fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=10,
        batch_no="EXP-7", biz_type="purchase_in",
        expiry_date=date.today() + timedelta(days=5),
    )
    alerts = fifo.expiry_alerts(session, tenant_id=tid, warehouse_id=src.id, days=90)
    assert isinstance(alerts, dict) and "items" in alerts
    assert any(
        i.get("batch_no") == "EXP-7" for i in alerts["items"]
    ), "5 天后到期的批次应被预警"


def test_trace_forward_returns_batch_and_flows(session: Session, tenant: Tenant) -> None:
    """正向追溯：从批次号查到入库流水。"""
    tid = tenant.id
    src, _, sku = _make_base(session)
    fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=20,
        batch_no="TRACE-1", biz_type="purchase_in",
    )
    fwd = trace.trace_forward(session, tenant_id=tid, batch_no="TRACE-1")
    assert fwd.get("batch"), "应返回批次信息"
    assert isinstance(fwd.get("flows"), list) and fwd["flows"], "应有入库流水"
    assert fwd["totals"]["in_qty"] == 20


def test_transfer_full_flow_keeps_both_books_equal(session: Session, tenant: Tenant) -> None:
    """调拨：建单 → 审核 → 执行，源仓减、目标仓增，两个仓的两本账都要平。"""
    tid = tenant.id
    src, dst, sku = _make_base(session)
    fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=50,
        batch_no="TRF-1", biz_type="purchase_in",
    )

    payload = SimpleNamespace(
        from_warehouse_id=src.id,
        to_warehouse_id=dst.id,
        from_location_id=None,
        to_location_id=None,
        reason="回归：调拨",
        remark="auto",
        transfer_no=None,
        items=[SimpleNamespace(sku_id=sku.id, qty=10, batch_no=None, material_id=None, remark=None)],
    )
    t = transfer.create_transfer(session, tid, payload, operator_id=None)
    assert t.transfer_no, "应自动生成调拨单号"
    assert t.status == transfer.STATUS_PENDING, "建单后应进入待审状态"

    transfer.approve_transfer(session, tid, t.id, operator_id=None)
    session.refresh(t)
    assert t.status == transfer.STATUS_APPROVED

    transfer.execute_transfer(session, tid, t.id, operator_id=None)
    session.refresh(t)
    assert t.status == transfer.STATUS_DONE

    assert book_qty(session, src.id, sku.id) == 40, "源仓应从 50 减到 40"
    assert book_qty(session, dst.id, sku.id) == 10, "目标仓应新增 10"
    assert_two_books_equal(session, tid, src.id, sku.id, "调拨后源仓")
    assert_two_books_equal(session, tid, dst.id, sku.id, "调拨后目标仓")


def test_issue_over_stock_rolls_back(session: Session, tenant: Tenant) -> None:
    """库存不足时必须整单失败，不能扣一半留个半截账。"""
    tid = tenant.id
    src, _, sku = _make_base(session)
    fifo.receive(
        session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=5,
        batch_no="SHORT-1", biz_type="purchase_in",
    )
    try:
        fifo.issue(
            session, tenant_id=tid, warehouse_id=src.id, sku_id=sku.id, qty=99,
            biz_type="ship_out",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("库存 5 出 99 应抛 ValueError")

    assert book_qty(session, src.id, sku.id) == 5, "失败后汇总账不能变"
    assert_two_books_equal(session, tid, src.id, sku.id, "出库失败后")
