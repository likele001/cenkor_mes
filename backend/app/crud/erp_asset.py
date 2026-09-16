# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""ERP 固定资产 CRUD"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.erp_asset import AssetCheck, AssetCheckItem, DepreciationRecord, FixedAsset


def list_assets(
    db: Session,
    tenant_id: int,
    *,
    category: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[FixedAsset]:
    stmt = select(FixedAsset).where(FixedAsset.tenant_id == tenant_id)
    if category:
        stmt = stmt.where(FixedAsset.category == category)
    if status:
        stmt = stmt.where(FixedAsset.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(FixedAsset.name.like(like) | FixedAsset.asset_no.like(like))
    stmt = stmt.order_by(FixedAsset.asset_no.asc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def count_assets(db: Session, tenant_id: int, **filters) -> int:
    stmt = select(FixedAsset.id).where(FixedAsset.tenant_id == tenant_id)
    if filters.get("category"):
        stmt = stmt.where(FixedAsset.category == filters["category"])
    if filters.get("status"):
        stmt = stmt.where(FixedAsset.status == filters["status"])
    return len(db.scalars(stmt).all())


def get_asset(db: Session, tenant_id: int, asset_id: int) -> FixedAsset | None:
    return db.scalar(select(FixedAsset).where(FixedAsset.tenant_id == tenant_id, FixedAsset.id == asset_id))


def asset_no_exists(db: Session, tenant_id: int, asset_no: str, exclude_id: int | None = None) -> bool:
    stmt = select(FixedAsset.id).where(FixedAsset.tenant_id == tenant_id, FixedAsset.asset_no == asset_no)
    if exclude_id:
        stmt = stmt.where(FixedAsset.id != exclude_id)
    return db.scalar(stmt) is not None


def create_asset(db: Session, tenant_id: int, data: dict, created_by: int | None = None) -> FixedAsset:
    a = FixedAsset(tenant_id=tenant_id, **data)
    a.accumulated_depreciation = Decimal("0")
    a.book_value = a.original_value
    a.monthly_depreciation = calc_monthly_depreciation(
        original_value=a.original_value,
        residual_value=a.residual_value,
        useful_life_months=a.useful_life_months,
        method=a.depreciation_method,
    )
    a.created_by = created_by
    db.add(a)
    db.flush()
    return a


def update_asset(db: Session, a: FixedAsset, data: dict) -> FixedAsset:
    recalc = False
    for k, v in data.items():
        if v is None:
            continue
        if k in ("original_value", "residual_value", "useful_life_months", "depreciation_method"):
            recalc = True
        if hasattr(a, k):
            setattr(a, k, v)
    if recalc:
        a.monthly_depreciation = calc_monthly_depreciation(
            original_value=a.original_value,
            residual_value=a.residual_value,
            useful_life_months=a.useful_life_months,
            method=a.depreciation_method,
        )
        a.book_value = (a.original_value or Decimal("0")) - (a.accumulated_depreciation or Decimal("0"))
    db.flush()
    return a


def delete_asset(db: Session, a: FixedAsset) -> None:
    db.delete(a)
    db.flush()


def calc_monthly_depreciation(*, original_value: Decimal, residual_value: Decimal, useful_life_months: int, method: str) -> Decimal:
    if not useful_life_months or method != "straight_line":
        return Decimal("0")
    return round((original_value - residual_value) / Decimal(str(useful_life_months)), 2)


def list_depreciation_records(db: Session, tenant_id: int, *, period: str | None = None, asset_id: int | None = None, offset: int = 0, limit: int = 50) -> list[DepreciationRecord]:
    stmt = select(DepreciationRecord).where(DepreciationRecord.tenant_id == tenant_id)
    if period:
        stmt = stmt.where(DepreciationRecord.period == period)
    if asset_id:
        stmt = stmt.where(DepreciationRecord.asset_id == asset_id)
    stmt = stmt.order_by(DepreciationRecord.period.desc(), DepreciationRecord.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def list_asset_depreciation(db: Session, tenant_id: int, asset_id: int) -> list[DepreciationRecord]:
    return list(
        db.scalars(
            select(DepreciationRecord)
            .where(DepreciationRecord.tenant_id == tenant_id, DepreciationRecord.asset_id == asset_id)
            .order_by(DepreciationRecord.period.asc())
        ).all()
    )


def get_depreciation_record(db: Session, tenant_id: int, asset_id: int, period: str) -> DepreciationRecord | None:
    return db.scalar(
        select(DepreciationRecord).where(
            DepreciationRecord.tenant_id == tenant_id,
            DepreciationRecord.asset_id == asset_id,
            DepreciationRecord.period == period,
        )
    )


def create_depreciation_record(db: Session, a: FixedAsset, period: str, amount: Decimal) -> DepreciationRecord:
    rec = DepreciationRecord(
        tenant_id=a.tenant_id,
        asset_id=a.id,
        period=period,
        depreciation_amount=amount,
        accumulated_depreciation=a.accumulated_depreciation + amount,
        book_value=(a.book_value or Decimal("0")) - amount,
    )
    db.add(rec)
    a.accumulated_depreciation = rec.accumulated_depreciation
    a.book_value = rec.book_value
    db.flush()
    return rec


# ---------- 盘点 ----------
def list_checks(db: Session, tenant_id: int, *, status: str | None = None, offset: int = 0, limit: int = 50) -> list[AssetCheck]:
    stmt = select(AssetCheck).where(AssetCheck.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(AssetCheck.status == status)
    stmt = stmt.order_by(AssetCheck.check_date.desc(), AssetCheck.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_check(db: Session, tenant_id: int, check_id: int) -> AssetCheck | None:
    return db.scalar(
        select(AssetCheck)
        .where(AssetCheck.tenant_id == tenant_id, AssetCheck.id == check_id)
        .options(selectinload(AssetCheck.items))
    )


def check_no_exists(db: Session, tenant_id: int, check_no: str) -> bool:
    return db.scalar(select(AssetCheck.id).where(AssetCheck.tenant_id == tenant_id, AssetCheck.check_no == check_no)) is not None


def create_check(db: Session, tenant_id: int, *, check_no: str, check_date: date, remark: str | None, items: list[dict], created_by: int | None) -> AssetCheck:
    ck = AssetCheck(
        tenant_id=tenant_id,
        check_no=check_no,
        check_date=check_date,
        status="draft",
        remark=remark,
        created_by=created_by,
    )
    ck.items = [
        AssetCheckItem(
            tenant_id=tenant_id,
            asset_id=it["asset_id"],
            expected_qty=it.get("expected_qty", 1),
            checked_qty=it.get("checked_qty", 1),
            diff_qty=(it.get("checked_qty", 1) or 0) - (it.get("expected_qty", 1) or 0),
            status="normal" if it.get("checked_qty", 1) == it.get("expected_qty", 1) else ("surplus" if it.get("checked_qty", 1) > it.get("expected_qty", 1) else "loss"),
            remark=it.get("remark"),
        )
        for it in items
    ]
    db.add(ck)
    db.flush()
    return ck


def update_check_items(db: Session, ck: AssetCheck, items: list[dict]) -> AssetCheck:
    ck.items.clear()
    ck.items = [
        AssetCheckItem(
            tenant_id=ck.tenant_id,
            asset_id=it["asset_id"],
            expected_qty=it.get("expected_qty", 1),
            checked_qty=it.get("checked_qty", 1),
            diff_qty=(it.get("checked_qty", 1) or 0) - (it.get("expected_qty", 1) or 0),
            status="normal" if it.get("checked_qty", 1) == it.get("expected_qty", 1) else ("surplus" if it.get("checked_qty", 1) > it.get("expected_qty", 1) else "loss"),
            remark=it.get("remark"),
        )
        for it in items
    ]
    db.flush()
    return ck


def complete_check(db: Session, ck: AssetCheck) -> AssetCheck:
    ck.status = "done"
    db.flush()
    return ck
