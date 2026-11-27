# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""完工入库：工单完工 → 成品入库闭环。

此前 `warehouse_entries.source_type` 只认 purchase/other，报工终审不会生成成品入库单，
车间报完还得仓管手工建「其他入库」选成品 SKU，发货才扣得到库存；也没有
「工单完工数 vs 实际入库数」的对账，超入/少入查不出来。
"""

import pytest

from app.crud.warehouse import get_stock
from app.crud.warehouse_entry import (
    cancel_entry,
    confirm_entry,
    create_entry,
    create_entry_from_work_order,
    ensure_work_order_entry,
    list_work_order_pending,
    work_order_entered_qty,
    work_order_finished_qty,
    work_order_remain_qty,
)
from app.models.warehouse import Warehouse
from app.models.warehouse_entry import WarehouseEntry, WarehouseEntryItem
from app.services.production_rollup import sync_work_order_progress


@pytest.fixture
def finished_wh(session) -> Warehouse:
    wh = Warehouse(code="WH-FIN-T", name="成品仓", is_active=True, is_finished=True)
    session.add(wh)
    session.flush()
    return wh


@pytest.fixture
def other_wh(session) -> Warehouse:
    wh = Warehouse(code="WH-MAT-T", name="原材料仓", is_active=True, is_finished=False)
    session.add(wh)
    session.flush()
    return wh


def _report(session, task, user, good_qty: int) -> None:
    from app.models.report import Report

    session.add(Report(
        task_id=task.id, report_user_id=user.id,
        good_qty=good_qty, bad_qty=0, status="qc_approved",
    ))
    session.flush()


def _auto_entry(session, work_order) -> WarehouseEntry:
    return session.query(WarehouseEntry).filter_by(work_order_id=work_order.id).one()


def _finish(session, wo, task, user, good_qty: int) -> None:
    """报工终审后把工单回卷到 done。"""
    _report(session, task, user, good_qty)
    session.flush()
    sync_work_order_progress(session, wo)
    session.refresh(wo)


# ────────────── 完工数量口径 ──────────────

def test_finished_qty_takes_last_task_not_sum(session, work_order, task, process, test_user):
    """多道工序各报一遍同一批产出，完工数取末道，不能求和。"""
    from app.models.task import Task

    t2 = Task(
        work_order_id=work_order.id, process_id=process.id, seq=2,
        task_code="T-CORE-002", planned_qty=100, status="pending",
    )
    session.add(t2)
    session.flush()
    _report(session, task, test_user, 100)
    _report(session, t2, test_user, 100)

    assert work_order_finished_qty(session, work_order.id) == 100


def test_finished_qty_zero_without_approved_report(session, work_order, task, test_user):
    from app.models.report import Report

    session.add(Report(task_id=task.id, report_user_id=test_user.id,
                       good_qty=50, bad_qty=0, status="leader_approved"))
    session.flush()
    assert work_order_finished_qty(session, work_order.id) == 0


# ────────────── 自动建单 ──────────────

def test_auto_entry_created_on_finish(session, work_order, task, test_user, finished_wh):
    _finish(session, work_order, task, test_user, 100)

    entry = session.query(WarehouseEntry).filter_by(work_order_id=work_order.id).one()
    assert entry.status == "draft"
    assert entry.source_type == "work_order"
    assert entry.warehouse_id == finished_wh.id
    assert entry.total_qty == 100
    # 成品入库只落 SKU：完工品通常没有物料主档
    assert entry.items[0].sku_id == work_order.sku_id
    assert entry.items[0].material_id is None


def test_auto_entry_idempotent(session, work_order, task, test_user, finished_wh):
    """反复回卷工单不重复建单。"""
    _finish(session, work_order, task, test_user, 100)
    sync_work_order_progress(session, work_order)
    sync_work_order_progress(session, work_order)

    assert session.query(WarehouseEntry).filter_by(work_order_id=work_order.id).count() == 1


def test_auto_entry_skipped_without_finished_warehouse(session, work_order, task, test_user, other_wh):
    """没有成品仓就不建单——把成品入到原材料仓比不入账更难查。"""
    _finish(session, work_order, task, test_user, 100)

    assert session.query(WarehouseEntry).filter_by(work_order_id=work_order.id).count() == 0
    # 缺口要能在待入库列表里看到
    rows = list_work_order_pending(session)
    assert [r["work_order_id"] for r in rows] == [work_order.id]
    assert rows[0]["remain_qty"] == 100


def test_auto_entry_skipped_when_not_finished(session, work_order, task, test_user, finished_wh):
    assert ensure_work_order_entry(session, work_order) is None


# ────────────── 数量约束 ──────────────

def test_entry_qty_capped_by_finished(session, work_order, task, test_user, finished_wh):
    _finish(session, work_order, task, test_user, 100)

    with pytest.raises(ValueError, match="超额"):
        create_entry(
            session, code="WE-T-OVER", source_type="work_order",
            warehouse_id=finished_wh.id,
            items=[{"material_id": None, "sku_id": work_order.sku_id, "qty": 101}],
            work_order_id=work_order.id,
        )


def test_entry_qty_rejects_not_done_work_order(session, work_order, task, test_user, finished_wh):
    _report(session, task, test_user, 100)  # 有报工但没回卷，工单仍是 open

    with pytest.raises(ValueError, match="完工后才能入库"):
        create_entry(
            session, code="WE-T-ND", source_type="work_order",
            warehouse_id=finished_wh.id,
            items=[{"material_id": None, "sku_id": work_order.sku_id, "qty": 10}],
            work_order_id=work_order.id,
        )


def test_confirm_blocks_duplicate_occupation(session, work_order, task, test_user, finished_wh):
    """两张草稿并发建单都能过（都读到已入库 0），重复占用必须在确认时拦住。"""
    _finish(session, work_order, task, test_user, 100)
    first = _auto_entry(session, work_order)

    # 模拟并发：绕过建单校验直接塞第二张同额草稿
    dup = WarehouseEntry(
        code="WE-T-DUP", status="draft", source_type="work_order",
        warehouse_id=finished_wh.id, work_order_id=work_order.id, total_qty=100,
    )
    dup.items = [WarehouseEntryItem(
        material_id=None, sku_id=work_order.sku_id, qty=100,
        unit_cost=0, cost_amount=0,
    )]
    session.add(dup)
    session.flush()

    confirm_entry(session, first)
    with pytest.raises(ValueError, match="超额"):
        confirm_entry(session, dup)


def test_confirm_increases_stock(session, work_order, task, test_user, finished_wh):
    _finish(session, work_order, task, test_user, 100)
    confirm_entry(session, _auto_entry(session, work_order))

    stock = get_stock(session, finished_wh.id, work_order.sku_id)
    assert stock is not None and stock.qty == 100
    assert work_order_remain_qty(session, work_order.id)["remain"] == 0
    assert list_work_order_pending(session) == []


def test_cancelled_entry_frees_quota(session, work_order, task, test_user, finished_wh):
    """取消的入库单不再占用额度，可以重新入库。"""
    _finish(session, work_order, task, test_user, 100)
    cancel_entry(session, _auto_entry(session, work_order))

    assert work_order_entered_qty(session, work_order.id) == 0
    again = create_entry_from_work_order(session, work_order.id)
    assert again.status == "draft" and again.total_qty == 100


# ────────────── 手动与差额 ──────────────

def test_partial_entry_and_pending_gap(session, work_order, task, test_user, finished_wh):
    _finish(session, work_order, task, test_user, 100)
    # 自动建的那张先取消，才能演示「只入一部分」
    cancel_entry(session, _auto_entry(session, work_order))

    entry = create_entry_from_work_order(session, work_order.id, qty=60)
    assert entry.total_qty == 60
    confirm_entry(session, entry)  # 草稿不占额度，确认后才算已入库

    rows = list_work_order_pending(session)
    assert len(rows) == 1
    assert rows[0]["finished_qty"] == 100
    assert rows[0]["entered_qty"] == 60
    assert rows[0]["remain_qty"] == 40

    confirm_entry(session, create_entry_from_work_order(session, work_order.id))
    assert list_work_order_pending(session) == []


def test_from_work_order_requires_finished_warehouse(session, work_order, task, test_user, other_wh):
    _finish(session, work_order, task, test_user, 100)

    with pytest.raises(ValueError, match="成品仓"):
        create_entry_from_work_order(session, work_order.id)
