"""批次正/反向追溯。"""

from __future__ import annotations

import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.material_issue import MaterialIssue, MaterialReturn
from app.models.purchase import PurchaseOrder
from app.models.shipment import Shipment
from app.models.sku import Sku
from app.models.user import User
from app.models.stocktake import Stocktake
from app.models.warehouse import StockBatch, StockLedger, WarehouseLocation
from app.models.warehouse_entry import WarehouseEntry
from app.models.work_order import WorkOrder

logger = logging.getLogger(__name__)

_REF_LABELS = {
    "material_issue": "领料单",
    "shipment": "发货单",
    "stock_check": "盘点单",
    "work_order": "工单",
}


def _work_order_code(ref_id: int) -> str:
    return f"WO-{ref_id:06d}"


def _resolve_ref_code(db: Session, tenant_id: int, ref_type: str | None, ref_id: int | None) -> str | None:
    """流水 ref_type/ref_id → 单据号。"""
    if not ref_type or ref_id is None:
        return None
    if ref_type == "material_issue":
        return db.scalar(
            select(MaterialIssue.code).where(
                MaterialIssue.id == ref_id
            )
        )
    if ref_type == "shipment":
        return db.scalar(
            select(Shipment.code).where(Shipment.id == ref_id)
        )
    if ref_type == "stock_check":
        return db.scalar(
            select(Stocktake.code).where(Stocktake.id == ref_id)
        )
    if ref_type == "work_order":
        exists = db.scalar(
            select(WorkOrder.id).where(WorkOrder.id == ref_id)
        )
        return _work_order_code(ref_id) if exists is not None else None
    if ref_type == "stock":
        return "存量回填"
    return None


def _resolve_source_code(db: Session, tenant_id: int, source_type: str | None, source_id: int | None) -> str | None:
    """批次来源 source_type/source_id → 来源单号。"""
    if not source_type or source_id is None:
        return None
    if source_type == "purchase_order":
        return db.scalar(
            select(PurchaseOrder.code).where(
                PurchaseOrder.id == source_id
            )
        )
    if source_type == "warehouse_entry":
        return db.scalar(
            select(WarehouseEntry.code).where(
                WarehouseEntry.id == source_id
            )
        )
    if source_type == "material_return":
        return db.scalar(
            select(MaterialReturn.code).where(
                MaterialReturn.id == source_id
            )
        )
    if source_type == "legacy":
        return "存量回填"
    return None


def _location_code(db: Session, tenant_id: int, location_id: int | None) -> str | None:
    if location_id is None:
        return None
    return db.scalar(
        select(WarehouseLocation.code).where(
            WarehouseLocation.id == location_id, WarehouseLocation.tenant_id == tenant_id
        )
    )


def trace_forward(db: Session, *, tenant_id: int, batch_no: str) -> dict:
    """批次号 → 全部流水 → 关联单据号。"""
    batch = db.scalar(
        select(StockBatch).where(
            StockBatch.tenant_id == tenant_id, StockBatch.batch_no == batch_no
        )
    )
    if batch is None:
        raise ValueError("批次不存在")

    sku = db.scalar(select(Sku).where(Sku.id == batch.sku_id))
    rows = db.execute(
        select(StockLedger, WarehouseLocation, User)
        .outerjoin(WarehouseLocation, WarehouseLocation.id == StockLedger.location_id)
        .outerjoin(User, User.id == StockLedger.operator_id)
        .where(StockLedger.tenant_id == tenant_id, StockLedger.batch_id == batch.id)
        .order_by(StockLedger.occurred_at.asc(), StockLedger.id.asc())
    ).all()

    flows: list[dict] = []
    in_qty = 0
    out_qty = 0
    for ledger, loc, operator in rows:
        if ledger.qty_delta >= 0:
            in_qty += int(ledger.qty_delta)
        else:
            out_qty += abs(int(ledger.qty_delta))
        flows.append(
            {
                "id": ledger.id,
                "occurred_at": ledger.occurred_at,
                "qty_delta": int(ledger.qty_delta),
                "biz_type": ledger.biz_type,
                "ref_type": ledger.ref_type,
                "ref_id": ledger.ref_id,
                "ref_code": _resolve_ref_code(db, tenant_id, ledger.ref_type, ledger.ref_id),
                "location_code": loc.code if loc else None,
                "operator_name": (operator.full_name or operator.username) if operator else None,
                "remark": ledger.remark,
            }
        )

    return {
        "batch": {
            "id": batch.id,
            "batch_no": batch.batch_no,
            "supplier_batch_no": batch.supplier_batch_no,
            "sku_id": batch.sku_id,
            "sku_code": sku.code if sku else None,
            "sku_name": sku.name if sku else None,
            "warehouse_id": batch.warehouse_id,
            "location_id": batch.location_id,
            "location_code": _location_code(db, tenant_id, batch.location_id),
            "mfg_date": batch.mfg_date,
            "expiry_date": batch.expiry_date,
            "qty_on_hand": int(batch.qty_on_hand or 0),
            "qty_reserved": int(batch.qty_reserved or 0),
            "available": max(0, int(batch.qty_on_hand or 0) - int(batch.qty_reserved or 0)),
            "status": batch.status,
            "source_type": batch.source_type,
            "source_id": batch.source_id,
        },
        "flows": flows,
        "totals": {
            "in_qty": in_qty,
            "out_qty": out_qty,
            "available": max(0, int(batch.qty_on_hand or 0) - int(batch.qty_reserved or 0)),
        },
    }


def trace_backward(db: Session, *, tenant_id: int, ref_type: str, ref_id: int) -> dict:
    """单据 → 消耗的批次清单（含供应商批次、生产日期、效期）。"""
    ref = {
        "ref_type": ref_type,
        "ref_id": ref_id,
        "ref_code": None,
        "ref_label": _REF_LABELS.get(ref_type),
    }

    stmt = select(StockLedger).where(
        StockLedger.tenant_id == tenant_id,
        StockLedger.qty_delta < 0,
    )
    if ref_type == "work_order":
        wo_id = db.scalar(
            select(WorkOrder.id).where(WorkOrder.id == ref_id)
        )
        if wo_id is not None:
            ref["ref_code"] = _work_order_code(ref_id)
        issue_ids = db.scalars(
            select(MaterialIssue.id).where( MaterialIssue.work_order_id == ref_id
            )
        ).all()
        conds = [and_(StockLedger.ref_type == "work_order", StockLedger.ref_id == ref_id)]
        if issue_ids:
            conds.append(
                and_(StockLedger.ref_type == "material_issue", StockLedger.ref_id.in_(issue_ids))
            )
        stmt = stmt.where(or_(*conds))
    else:
        ref["ref_code"] = _resolve_ref_code(db, tenant_id, ref_type, ref_id)
        stmt = stmt.where(StockLedger.ref_type == ref_type, StockLedger.ref_id == ref_id)

    ledgers = db.scalars(stmt.order_by(StockLedger.id.asc())).all()

    # 按批次聚合消耗量，取最近一条流水的库位与时间
    agg: dict[int, dict] = {}
    for ledger in ledgers:
        entry = agg.get(ledger.batch_id)
        if entry is None:
            agg[ledger.batch_id] = {
                "qty": abs(int(ledger.qty_delta)),
                "location_id": ledger.location_id,
                "occurred_at": ledger.occurred_at,
            }
        else:
            entry["qty"] += abs(int(ledger.qty_delta))
            if ledger.occurred_at and (entry["occurred_at"] is None or ledger.occurred_at >= entry["occurred_at"]):
                entry["occurred_at"] = ledger.occurred_at
                entry["location_id"] = ledger.location_id

    batches: list[dict] = []
    total_qty = 0
    if agg:
        batch_rows = db.scalars(
            select(StockBatch).where(
                StockBatch.tenant_id == tenant_id, StockBatch.id.in_(list(agg))
            )
        ).all()
        batch_map = {b.id: b for b in batch_rows}
        sku_ids = {b.sku_id for b in batch_rows}
        sku_map = {
            s.id: s
            for s in db.scalars(
                select(Sku).where(Sku.id.in_(sku_ids))
            ).all()
        } if sku_ids else {}
        location_ids = {v["location_id"] for v in agg.values() if v["location_id"] is not None}
        loc_map = {
            loc.id: loc
            for loc in db.scalars(
                select(WarehouseLocation).where(
                    WarehouseLocation.tenant_id == tenant_id, WarehouseLocation.id.in_(location_ids)
                )
            ).all()
        } if location_ids else {}

        for batch_id, entry in agg.items():
            batch = batch_map.get(batch_id)
            if batch is None:
                continue
            sku = sku_map.get(batch.sku_id)
            loc = loc_map.get(entry["location_id"])
            total_qty += entry["qty"]
            batches.append(
                {
                    "batch_id": batch.id,
                    "batch_no": batch.batch_no,
                    "supplier_batch_no": batch.supplier_batch_no,
                    "mfg_date": batch.mfg_date,
                    "expiry_date": batch.expiry_date,
                    "sku_id": batch.sku_id,
                    "sku_code": sku.code if sku else None,
                    "sku_name": sku.name if sku else None,
                    "warehouse_id": batch.warehouse_id,
                    "location_code": loc.code if loc else None,
                    "qty": entry["qty"],
                    "source_type": batch.source_type,
                    "source_id": batch.source_id,
                    "source_code": _resolve_source_code(
                        db, tenant_id, batch.source_type, batch.source_id
                    ),
                    "occurred_at": entry["occurred_at"],
                }
            )

    return {
        "ref": ref,
        "batches": batches,
        "totals": {"batch_count": len(batches), "qty": total_qty},
    }
