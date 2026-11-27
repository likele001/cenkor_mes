# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.warehouse import adjust_stock
from app.crud.approval_record import record_status
from app.crud.locking import lock_row
from app.models.material import Material
from app.models.material_issue import MaterialReturn
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sku import Sku
from app.models.task import Task
from app.models.warehouse import Warehouse
from app.models.warehouse_entry import WarehouseEntry, WarehouseEntryItem
from app.models.work_order import WorkOrder


# 真正入账、占用完工额度的状态。草稿不占：作废的草稿若把额度锁死，
# 只能在库里改数据才能解开（对账单踩过同一个坑，这里从设计上避开）
ENTRY_BILLED_STATUSES = ("confirmed",)
# 未取消状态，仅用于「这张工单是否已经建过入库单」的防重复判断
ENTRY_ALIVE_STATUSES = ("draft", "confirmed")
# 成品仓缺失时的兜底编码（老库沿用 WH-FIN）
DEFAULT_FINISHED_WAREHOUSE_CODE = "WH-FIN"


def resolve_finished_warehouse_id(db: Session) -> int | None:
    """找成品仓：显式标记优先，其次沿用 WH-FIN 编码，都没有就返回 None。

    返回 None 时调用方不得凭空挑一个仓库——把成品入到原材料仓比不入账更难查。
    """
    wh = db.scalar(
        select(Warehouse)
        .where(Warehouse.is_finished.is_(True), Warehouse.is_active.is_(True))
        .order_by(Warehouse.id)
    )
    if wh is not None:
        return wh.id
    wh = db.scalar(
        select(Warehouse)
        .where(
            Warehouse.code == DEFAULT_FINISHED_WAREHOUSE_CODE,
            Warehouse.is_active.is_(True),
        )
    )
    return wh.id if wh is not None else None


def work_order_finished_qty(db: Session, work_order_id: int) -> int:
    """工单完工良品数 = 末道工序终审通过的合格数。

    取末道而不是各工序求和：每道工序都报一遍同一批产出，求和会把 100 件算成 500 件。
    """
    from app.services.production_rollup import task_done_qty

    last = db.scalar(
        select(Task)
        .where(Task.work_order_id == work_order_id)
        .order_by(Task.seq.desc())
        .limit(1)
    )
    if last is None:
        return 0
    return int(task_done_qty(db, last.id) or 0)


def work_order_entered_qty(db: Session, work_order_id: int, *, exclude_entry_id: int | None = None) -> int:
    """该工单已确认入库的数量合计（草稿不计，取消不计）。"""
    stmt = select(WarehouseEntryItem.qty).join(
        WarehouseEntry, WarehouseEntry.id == WarehouseEntryItem.entry_id
    ).where(
        WarehouseEntry.work_order_id == work_order_id,
        WarehouseEntry.status.in_(ENTRY_BILLED_STATUSES),
    )
    if exclude_entry_id is not None:
        stmt = stmt.where(WarehouseEntry.id != exclude_entry_id)
    return int(sum(db.scalars(stmt).all()) or 0)


def work_order_draft_entry(db: Session, work_order_id: int) -> WarehouseEntry | None:
    """该工单已有的草稿入库单（用于提示「先确认这张」而不是再建一张）。"""
    return db.scalar(
        select(WarehouseEntry)
        .where(
            WarehouseEntry.work_order_id == work_order_id,
            WarehouseEntry.status == "draft",
        )
        .order_by(WarehouseEntry.id.desc())
    )


def work_order_remain_qty(db: Session, work_order_id: int) -> dict[str, int]:
    finished = work_order_finished_qty(db, work_order_id)
    entered = work_order_entered_qty(db, work_order_id)
    return {"finished": finished, "entered": entered, "remain": max(finished - entered, 0)}


def _check_work_order_qty(db: Session, work_order_id: int, wanted_total: int, *, exclude_entry_id: int | None = None) -> WorkOrder:
    """按工单入库不得超过完工良品数（建单时拦一道，确认时再拦一道）。"""
    wo = db.get(WorkOrder, work_order_id)
    if wo is None:
        raise ValueError("工单不存在")
    if wo.status != "done":
        raise ValueError(f"工单 #{wo.id} 当前为 {wo.status}，完工后才能入库")
    finished = work_order_finished_qty(db, wo.id)
    if finished <= 0:
        raise ValueError(f"工单 #{wo.id} 没有终审通过的完工数量，不能入库")
    entered = work_order_entered_qty(db, wo.id, exclude_entry_id=exclude_entry_id)
    if wanted_total > finished - entered:
        raise ValueError(
            f"工单 #{wo.id} 完工 {finished}，已入库 {entered}，本次 {wanted_total} 超额"
        )
    return wo


def _reject_return_entry(material_return_id: int | None) -> None:
    """退料回补由退料单确认时完成，入库单再走一次就是同一批料入两遍账。"""
    if material_return_id is not None:
        raise ValueError("退料入库请直接在退料单上确认，系统会回补库存，不要再建入库单")


def _check_purchase_qty(db: Session, purchase_order_id: int, wanted: dict[int, int]) -> PurchaseOrder:
    """入库数量必须落在采购单的未入库余量内，超出就直接拦下（建单时拦一次，确认时再拦一次）。"""
    po = db.get(PurchaseOrder, purchase_order_id)
    if not po:
        raise ValueError("采购单不存在")
    if po.status not in {"confirmed", "partial_received"}:
        raise ValueError(f"采购单 {po.code} 当前为 {po.status}，不允许入库")
    remain_by_material = {it.material_id: it.qty - it.received_qty for it in (po.items or [])}
    for material_id, qty in wanted.items():
        m = db.get(Material, material_id)
        name = m.name if m else f"物料#{material_id}"
        if material_id not in remain_by_material:
            raise ValueError(f"物料「{name}」不在采购单 {po.code} 中")
        if qty > remain_by_material[material_id]:
            raise ValueError(f"物料「{name}」入库 {qty} 超出采购未入库 {remain_by_material[material_id]}")
    return po


def _commit_purchase_receipt(db: Session, po: PurchaseOrder, entry: WarehouseEntry) -> None:
    """入库单确认后核销回采购单：推进 received_qty 与采购单状态，跟采购页「直接入库」同一口径。"""
    for it in entry.items:
        po_item = db.scalar(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.order_id == po.id,
                PurchaseOrderItem.material_id == it.material_id,
            )
        )
        po_item.received_qty += it.qty
    total_qty = sum(i.qty for i in po.items)
    total_received = sum(i.received_qty for i in po.items)
    po.status = "received" if total_received >= total_qty else "partial_received"
    db.flush()


def get_entry_by_id(db: Session, entry_id: int, with_items: bool = True) -> WarehouseEntry | None:
    q = select(WarehouseEntry)
    if with_items:
        q = q.options(
            selectinload(WarehouseEntry.items).selectinload(WarehouseEntryItem.material),
            selectinload(WarehouseEntry.items).selectinload(WarehouseEntryItem.sku),
            selectinload(WarehouseEntry.warehouse),
            selectinload(WarehouseEntry.purchase_order),
            selectinload(WarehouseEntry.material_return),
            selectinload(WarehouseEntry.work_order),
        )
    return db.scalar(q.where(WarehouseEntry.id == entry_id))


def list_entries(
    db: Session,
    warehouse_id: int | None = None,
    source_type: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[WarehouseEntry]:
    stmt = select(WarehouseEntry).options(
        selectinload(WarehouseEntry.warehouse),
        selectinload(WarehouseEntry.purchase_order),
        selectinload(WarehouseEntry.material_return),
        selectinload(WarehouseEntry.work_order),
    )
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseEntry.warehouse_id == warehouse_id)
    if source_type:
        stmt = stmt.where(WarehouseEntry.source_type == source_type)
    if status:
        stmt = stmt.where(WarehouseEntry.status == status)
    stmt = stmt.order_by(WarehouseEntry.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def _resolve_cost(db: Session, sku_id: int) -> Decimal:
    cost = Decimal("0")
    if sku_id:
        sku = db.get(Sku, sku_id)
        if sku and sku.cost_price:
            cost = Decimal(str(sku.cost_price))
    return cost


def create_entry(
    db: Session,
    code: str,
    source_type: str,
    warehouse_id: int,
    items: list[dict],
    purchase_order_id: int | None = None,
    material_return_id: int | None = None,
    work_order_id: int | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> WarehouseEntry:
    _reject_return_entry(material_return_id)
    if source_type == "purchase" and purchase_order_id is None:
        raise ValueError("采购入库必须关联采购单")
    if source_type == "work_order" and work_order_id is None:
        raise ValueError("工单完工入库必须关联工单")
    if work_order_id is not None and source_type != "work_order":
        raise ValueError("关联工单的入库单，入库类型必须是工单完工入库")
    total_wanted = 0
    # 采购按物料核销，工单按 SKU 核销（成品可能没有物料主档）
    wanted: dict[int, int] = {}
    wanted_by_sku: dict[int, int] = {}
    for it in items:
        qty = int(it["qty"])
        if qty <= 0:
            raise ValueError("入库数量必须大于 0")
        if source_type == "purchase" and it.get("material_id") is None:
            raise ValueError("采购入库的明细必须指定物料")
        if it.get("material_id") is not None:
            wanted[it["material_id"]] = wanted.get(it["material_id"], 0) + qty
        wanted_by_sku[it["sku_id"]] = wanted_by_sku.get(it["sku_id"], 0) + qty
        total_wanted += qty
    if purchase_order_id is not None:
        if source_type != "purchase":
            raise ValueError("关联采购单的入库单，入库类型必须是采购入库")
        _check_purchase_qty(db, purchase_order_id, wanted)
    if work_order_id is not None:
        _check_work_order_qty(db, work_order_id, total_wanted)
    entry = WarehouseEntry(
        code=code,
        source_type=source_type,
        warehouse_id=warehouse_id,
        purchase_order_id=purchase_order_id,
        material_return_id=material_return_id,
        work_order_id=work_order_id,
        remark=remark,
        created_by=created_by,
    )
    entry_items = []
    total_qty = 0
    total_cost = Decimal("0")
    for it in items:
        material_id = it.get("material_id")
        sku_id = it["sku_id"]
        qty = int(it["qty"])
        unit_cost = _resolve_cost(db, sku_id)
        total_qty += qty
        total_cost += unit_cost * qty
        entry_items.append(WarehouseEntryItem(
            material_id=material_id, sku_id=sku_id,
            qty=qty, unit_cost=unit_cost, cost_amount=unit_cost * qty,
        ))
    entry.items = entry_items
    entry.total_qty = total_qty
    entry.total_cost = total_cost
    db.add(entry)
    db.flush()
    return entry


def confirm_entry(db: Session, entry: WarehouseEntry, confirmed_by: int | None = None, *, channel: str = "web") -> WarehouseEntry:
    entry = lock_row(db, WarehouseEntry, entry.id)
    if entry is None:
        raise ValueError("入库单不存在")
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许确认")
    _reject_return_entry(entry.material_return_id)
    po = None
    if entry.purchase_order_id is not None:
        totals: dict[int, int] = {}
        for it in entry.items:
            if it.material_id is None:
                raise ValueError("采购入库的明细必须指定物料")
            totals[it.material_id] = totals.get(it.material_id, 0) + it.qty
        po = _check_purchase_qty(db, entry.purchase_order_id, totals)
    if entry.work_order_id is not None:
        # 草稿不占额度，两张草稿可能勾中同一张工单，重复占用必须在确认这一刻拦住：
        # 否则同一批完工品会被入两遍库存，凭空多出一堆账面成品
        _check_work_order_qty(
            db, entry.work_order_id, int(entry.total_qty or 0), exclude_entry_id=entry.id,
        )
    for it in entry.items:
        adjust_stock(
            db,
            warehouse_id=entry.warehouse_id,
            sku_id=it.sku_id,
            change_qty=it.qty,
            biz_type="warehouse_entry",
            biz_id=entry.id,
            remark=entry.code,
        )
    entry.status = "confirmed"
    entry.confirmed_at = datetime.now()
    entry.confirmed_by = confirmed_by
    if po is not None:
        _commit_purchase_receipt(db, po, entry)
    record_status(
        db,
        biz_type="warehouse_entry",
        biz_id=entry.id,
        biz_code=entry.code,
        action="confirm",
        operator=confirmed_by,
        from_status="draft",
        to_status=entry.status,
        channel=channel,
        detail={"total_qty": entry.total_qty, "total_cost": str(entry.total_cost)},
    )
    db.flush()
    return entry


def cancel_entry(db: Session, entry: WarehouseEntry, *, operator_id: int | None = None, channel: str = "web") -> WarehouseEntry:
    entry = lock_row(db, WarehouseEntry, entry.id)
    if entry is None:
        raise ValueError("入库单不存在")
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许取消")
    entry.status = "cancelled"
    record_status(
        db,
        biz_type="warehouse_entry",
        biz_id=entry.id,
        biz_code=entry.code,
        action="cancel",
        operator=operator_id,
        from_status="draft",
        to_status=entry.status,
        channel=channel,
    )
    db.flush()
    return entry


# ────────────────────────── 工单完工入库 ──────────────────────────

def ensure_work_order_entry(
    db: Session,
    wo: WorkOrder,
    *,
    warehouse_id: int | None = None,
    created_by: int | None = None,
) -> WarehouseEntry | None:
    """工单首次完工时自动生成一张草稿入库单；已有未取消单据则跳过。

    幂等靠「该工单是否已有未取消入库单」判断，而不是比对数量：报工终审会反复回卷
    工单状态，每次都比数量就会反复补单。差额场景由 list_work_order_pending +
    手动一键入库处理。

    返回 None 表示不需要/无法建单（未完工、无完工数、已建过、找不到成品仓），
    这不是错误——差异会在待入库列表里如实显示。
    """
    if wo.status != "done":
        return None
    remain = work_order_remain_qty(db, wo.id)
    if remain["remain"] <= 0:
        return None
    exists = db.scalar(
        select(WarehouseEntry.id).where(
            WarehouseEntry.work_order_id == wo.id,
            WarehouseEntry.status.in_(ENTRY_ALIVE_STATUSES),
        )
    )
    if exists is not None:
        return None
    wh_id = warehouse_id or resolve_finished_warehouse_id(db)
    if wh_id is None:
        return None
    return _create_work_order_entry(db, wo, wh_id, remain["remain"], created_by=created_by)


def _create_work_order_entry(
    db: Session,
    wo: WorkOrder,
    warehouse_id: int,
    qty: int,
    *,
    created_by: int | None = None,
) -> WarehouseEntry:
    from app.services.code_generator import BizType, resolve_code

    code = resolve_code(
        db,
        biz_type=BizType.WAREHOUSE_ENTRY,
        code=None,
        exists=lambda c: db.scalar(select(WarehouseEntry.id).where(WarehouseEntry.code == c)) is not None,
    )
    order_code = wo.order.code if getattr(wo, "order", None) is not None else None
    remark = f"工单完工自动入库（订单 {order_code}）" if order_code else "工单完工自动入库"
    return create_entry(
        db,
        code=code,
        source_type="work_order",
        warehouse_id=warehouse_id,
        # 成品入库只落 SKU：完工品常常没有物料主档，硬要物料号就建不出单
        items=[{"material_id": None, "sku_id": wo.sku_id, "qty": int(qty)}],
        work_order_id=wo.id,
        remark=remark,
        created_by=created_by,
    )


def create_entry_from_work_order(
    db: Session,
    work_order_id: int,
    *,
    warehouse_id: int | None = None,
    qty: int | None = None,
    created_by: int | None = None,
) -> WarehouseEntry:
    """手动按工单建入库单：默认按剩余未入库量全入，也可只入一部分。"""
    wo = db.get(WorkOrder, work_order_id)
    if wo is None:
        raise ValueError("工单不存在")
    if wo.status != "done":
        raise ValueError(f"工单 #{wo.id} 当前为 {wo.status}，完工后才能入库")
    remain = work_order_remain_qty(db, wo.id)
    if remain["remain"] <= 0:
        raise ValueError(f"工单 #{wo.id} 完工 {remain['finished']}，已全部入库")
    take = remain["remain"] if qty is None else int(qty)
    if take <= 0:
        raise ValueError("入库数量必须大于 0")
    if take > remain["remain"]:
        raise ValueError(f"工单 #{wo.id} 待入库 {remain['remain']}，本次 {take} 超额")
    draft = work_order_draft_entry(db, wo.id)
    if draft is not None:
        raise ValueError(f"工单 #{wo.id} 已有草稿入库单 {draft.code}，请直接确认或取消它")
    wh_id = warehouse_id or resolve_finished_warehouse_id(db)
    if wh_id is None:
        raise ValueError("未设置成品仓，请先在仓库管理中把某个仓库标记为成品仓")
    wh = db.get(Warehouse, wh_id)
    if wh is None or not wh.is_active:
        raise ValueError("成品仓不存在或已停用")
    return _create_work_order_entry(db, wo, wh_id, take, created_by=created_by)


def _pending_rows(db: Session) -> list[dict]:
    """已完工但未足额入库的工单：完工数 / 已入库 / 待入库。

    逐单计算（每单一次末道工序 + 一次入库汇总），done 工单量级有限，
    比起把 max(整批报工, 逐件报工) 塞进一条 SQL，可读性更重要。
    """
    from sqlalchemy.orm import selectinload

    wos = db.scalars(
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.sku),
            selectinload(WorkOrder.order),
        )
        .where(WorkOrder.status == "done")
        .order_by(WorkOrder.id.desc())
    ).all()
    rows: list[dict] = []
    for wo in wos:
        qty = work_order_remain_qty(db, wo.id)
        if qty["remain"] <= 0:
            continue
        draft = work_order_draft_entry(db, wo.id)
        rows.append({
            "work_order_id": wo.id,
            "order_id": wo.order_id,
            "order_code": wo.order.code if wo.order is not None else None,
            "draft_entry_id": draft.id if draft is not None else None,
            "draft_entry_code": draft.code if draft is not None else None,
            "sku_id": wo.sku_id,
            "sku_code": wo.sku.code if wo.sku is not None else None,
            "sku_name": wo.sku.name if wo.sku is not None else None,
            "plan_qty": int(wo.qty or 0),
            "finished_qty": qty["finished"],
            "entered_qty": qty["entered"],
            "remain_qty": qty["remain"],
            "finished_at": wo.finished_at.isoformat() if wo.finished_at else None,
        })
    return rows


def list_work_order_pending(db: Session, offset: int = 0, limit: int = 100) -> list[dict]:
    return _pending_rows(db)[offset:offset + limit]


def count_work_order_pending(db: Session) -> int:
    return len(_pending_rows(db))
