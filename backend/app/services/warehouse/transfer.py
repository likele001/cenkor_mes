"""库区不涉及库存；本模块只处理仓间 / 库位间调拨。

约束：
- 批次扣减与台账写入全部复用 `services.warehouse.fifo`（issue / receive / list_available），
  不直接 UPDATE stocks，也不绕过 StockLedger；
- 数量统一使用 Decimal，落库前换算为整数（StockBatch 数量为整数）。
"""

from datetime import date, datetime
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

# 批次冻结表只在装了质量模块的宿主上存在；单用户版没有这张表，
# 降级为「无冻结批次」—— 冻结判断还有 stock_batch.status 一层兜底。
try:  # pragma: no cover
    from app.models.quality_poka import BatchHold
except ImportError:  # pragma: no cover
    BatchHold = None  # type: ignore[assignment,misc]
from app.models.warehouse import (
    StockBatch,
    StockTransfer,
    StockTransferItem,
    Warehouse,
    WarehouseLocation,
)
from app.services.code_generator import BizType, resolve_code
from app.services.warehouse import fifo

logger = logging.getLogger(__name__)

STATUS_DRAFT = "draft"
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

_CANCELLABLE = {STATUS_DRAFT, STATUS_PENDING, STATUS_APPROVED}


def _qty_int(value) -> int:
    qty = Decimal(str(value))
    if qty <= 0:
        raise ValueError("调拨数量必须大于 0")
    if qty != qty.to_integral_value():
        raise ValueError("库存数量必须为整数")
    return int(qty)


def _get_transfer(db: Session, tenant_id: int, transfer_id: int, *, lock: bool = False) -> StockTransfer:
    stmt = select(StockTransfer).where(
        StockTransfer.id == transfer_id,
        StockTransfer.tenant_id == tenant_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    transfer = db.scalar(stmt)
    if transfer is None:
        raise ValueError("调拨单不存在")
    return transfer


def _ensure_warehouse(db: Session, tenant_id: int, warehouse_id: int) -> Warehouse:
    wh = db.scalar(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    if wh is None:
        raise ValueError("仓库不存在")
    return wh


def _ensure_location(
    db: Session, tenant_id: int, warehouse_id: int, location_id: int | None
) -> WarehouseLocation | None:
    if location_id is None:
        return None
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.id == location_id,
            WarehouseLocation.tenant_id == tenant_id,
            WarehouseLocation.warehouse_id == warehouse_id,
        )
    )
    if loc is None:
        raise ValueError("库位不存在或不属于该仓库")
    return loc


def _held_batch_ids(db: Session, tenant_id: int, batch_ids: list[int]) -> set[int]:
    if not batch_ids or BatchHold is None:
        return set()
    return set(
        db.scalars(
            select(BatchHold.stock_batch_id).where(
                BatchHold.status == "held",
                BatchHold.stock_batch_id.in_(batch_ids),
            )
        ).all()
    )


def _source_allocations(
    db: Session,
    *,
    tenant_id: int,
    from_warehouse_id: int,
    from_location_id: int | None,
    sku_id: int,
    batch_no: str | None,
    qty: int,
) -> list[dict]:
    """复用 fifo.list_available 的 FIFO 排序，按源库位 / 指定批次过滤后凑齐数量。"""
    rows = fifo.list_available(
        db, tenant_id=tenant_id, warehouse_id=from_warehouse_id, sku_id=sku_id
    )
    wanted_batch = (batch_no or "").strip()
    today = date.today()
    held = _held_batch_ids(db, tenant_id, [int(r["batch_id"]) for r in rows])

    plan: list[dict] = []
    remaining = qty
    for row in rows:
        if remaining <= 0:
            break
        if from_location_id is not None and row["location_id"] != from_location_id:
            continue
        if wanted_batch and row["batch_no"] != wanted_batch:
            continue
        if int(row["batch_id"]) in held:
            continue
        expiry = row.get("expiry_date")
        if expiry is not None and expiry < today:
            continue
        take = min(int(row["available"]), remaining)
        if take <= 0:
            continue
        plan.append(
            {
                "batch_id": int(row["batch_id"]),
                "batch_no": row["batch_no"],
                "qty": take,
                "expiry_date": expiry,
                "mfg_date": row.get("mfg_date"),
                "supplier_batch_no": row.get("supplier_batch_no"),
            }
        )
        remaining -= take

    if remaining > 0:
        if wanted_batch:
            raise ValueError(f"批次 {wanted_batch} 可用量不足或已冻结/过期")
        raise ValueError("源库存可用量不足（已扣除冻结量）")
    return plan


def create_transfer(db: Session, tenant_id: int, payload, *, operator_id: int | None = None) -> StockTransfer:
    from_wh = _ensure_warehouse(db, tenant_id, payload.from_warehouse_id)
    to_wh = _ensure_warehouse(db, tenant_id, payload.to_warehouse_id)
    _ensure_location(db, tenant_id, from_wh.id, payload.from_location_id)
    _ensure_location(db, tenant_id, to_wh.id, payload.to_location_id)

    if from_wh.id == to_wh.id and payload.from_location_id == payload.to_location_id:
        raise ValueError("源库位与目标库位不能相同")
    if not payload.items:
        raise ValueError("调拨明细不能为空")

    transfer_no = resolve_code(
        db,
        biz_type=BizType.STOCK_TRANSFER,
        code=getattr(payload, "transfer_no", None),
        exists=lambda code: db.scalar(
            select(StockTransfer.id).where(
                StockTransfer.tenant_id == tenant_id,
                StockTransfer.transfer_no == code,
            )
        )
        is not None,
        duplicate_msg="调拨单号已存在",
    )

    transfer = StockTransfer(
        tenant_id=tenant_id,
        transfer_no=transfer_no,
        from_warehouse_id=from_wh.id,
        from_location_id=payload.from_location_id,
        to_warehouse_id=to_wh.id,
        to_location_id=payload.to_location_id,
        status=STATUS_PENDING,
        reason=payload.reason,
        remark=payload.remark,
        created_by=operator_id,
    )
    db.add(transfer)
    db.flush()

    for row in payload.items:
        qty = _qty_int(row.qty)
        sku_id = int(row.sku_id)
        batch_no = (row.batch_no or "").strip() or None
        plan = _source_allocations(
            db,
            tenant_id=tenant_id,
            from_warehouse_id=from_wh.id,
            from_location_id=payload.from_location_id,
            sku_id=sku_id,
            batch_no=batch_no,
            qty=qty,
        )
        item = StockTransferItem(
            tenant_id=tenant_id,
            transfer_id=transfer.id,
            sku_id=sku_id,
            material_id=row.material_id,
            batch_no=batch_no,
            qty=Decimal(qty),
            from_batch_id=plan[0]["batch_id"] if len(plan) == 1 else None,
            remark=row.remark,
        )
        db.add(item)
    db.flush()
    return transfer


def approve_transfer(
    db: Session, tenant_id: int, transfer_id: int, *, operator_id: int
) -> StockTransfer:
    transfer = _get_transfer(db, tenant_id, transfer_id, lock=True)
    if transfer.status == STATUS_APPROVED:
        return transfer
    if transfer.status != STATUS_PENDING:
        raise ValueError("仅待审批的调拨单可审批")
    transfer.status = STATUS_APPROVED
    transfer.approved_by = operator_id
    transfer.approved_at = datetime.now()
    db.flush()
    return transfer


def execute_transfer(
    db: Session, tenant_id: int, transfer_id: int, *, operator_id: int
) -> StockTransfer:
    transfer = _get_transfer(db, tenant_id, transfer_id, lock=True)
    # 幂等：已执行直接返回，不重复扣减
    if transfer.status == STATUS_DONE:
        return transfer
    if transfer.status != STATUS_APPROVED:
        raise ValueError("调拨单未审批，不能执行")

    items = list(
        db.scalars(
            select(StockTransferItem)
            .where(
                StockTransferItem.tenant_id == tenant_id,
                StockTransferItem.transfer_id == transfer.id,
            )
            .order_by(StockTransferItem.id.asc())
        ).all()
    )
    if not items:
        raise ValueError("调拨明细为空")

    # 先整单校验（冻结 / 效期 / 可用量），全部通过后再落库存，避免部分执行
    plans: dict[int, list[dict]] = {}
    for item in items:
        plans[item.id] = _source_allocations(
            db,
            tenant_id=tenant_id,
            from_warehouse_id=transfer.from_warehouse_id,
            from_location_id=transfer.from_location_id,
            sku_id=item.sku_id,
            batch_no=item.batch_no,
            qty=_qty_int(item.qty),
        )

    for item in items:
        plan = plans[item.id]
        remark = f"调拨 {transfer.transfer_no}"
        fifo.issue(
            db,
            tenant_id=tenant_id,
            warehouse_id=transfer.from_warehouse_id,
            sku_id=item.sku_id,
            qty=_qty_int(item.qty),
            allocations=[{"batch_id": p["batch_id"], "qty": p["qty"]} for p in plan],
            biz_type="transfer_out",
            ref_type="stock_transfer",
            ref_id=transfer.id,
            operator_id=operator_id,
            remark=remark,
        )
        first_target_id: int | None = None
        for p in plan:
            target = fifo.receive(
                db,
                tenant_id=tenant_id,
                warehouse_id=transfer.to_warehouse_id,
                sku_id=item.sku_id,
                qty=p["qty"],
                batch_no=p["batch_no"],
                location_id=transfer.to_location_id,
                mfg_date=p.get("mfg_date"),
                expiry_date=p.get("expiry_date"),
                supplier_batch_no=p.get("supplier_batch_no"),
                status="qualified",
                source_type="stock_transfer",
                source_id=transfer.id,
                operator_id=operator_id,
                biz_type="transfer_in",
                ref_type="stock_transfer",
                ref_id=transfer.id,
                remark=remark,
            )
            if first_target_id is None:
                first_target_id = target.id
        item.from_batch_id = plan[0]["batch_id"] if len(plan) == 1 else None
        item.to_batch_id = first_target_id

    transfer.status = STATUS_DONE
    transfer.done_at = datetime.now()
    db.flush()

    # 开放平台模块只在装了开放平台的宿主上存在。先做导入预检再埋点：
    # 模块缺失属于「这个能力不存在」，交给 except 打 traceback 会把每次调拨
    # 都刷成一条 ERROR，日志噪音会盖住真正的问题。
    try:
        from app.services.openapi.webhook import emit_event
    except ImportError:  # pragma: no cover —— 单用户版默认没有开放平台
        emit_event = None  # type: ignore[assignment]

    if emit_event is not None:
        try:
            emit_event(
                db,
                tenant_id,
                "stock.transferred",
                {
                    "transfer_id": transfer.id,
                    "transfer_no": transfer.transfer_no,
                    "from_warehouse_id": transfer.from_warehouse_id,
                    "to_warehouse_id": transfer.to_warehouse_id,
                    "item_count": len(items),
                    "total_qty": str(sum(_qty_int(i.qty) for i in items)),
                },
            )
        except Exception:  # noqa: BLE001 —— 埋点失败不影响库存主流程
            logger.warning(
                "emit stock.transferred failed tenant=%s transfer=%s", tenant_id, transfer.id
            )
    return transfer


def cancel_transfer(db: Session, tenant_id: int, transfer_id: int) -> StockTransfer:
    transfer = _get_transfer(db, tenant_id, transfer_id, lock=True)
    if transfer.status == STATUS_CANCELLED:
        return transfer
    if transfer.status not in _CANCELLABLE:
        raise ValueError("已执行的调拨单不可取消")
    transfer.status = STATUS_CANCELLED
    db.flush()
    return transfer