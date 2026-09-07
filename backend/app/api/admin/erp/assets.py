from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_asset import (
    asset_no_exists,
    check_no_exists,
    complete_check,
    count_assets,
    create_asset,
    create_check,
    create_depreciation_record,
    delete_asset,
    get_asset,
    get_check,
    get_depreciation_record,
    list_asset_depreciation,
    list_assets,
    list_checks,
    list_depreciation_records,
    update_asset,
    update_check_items,
)
from app.models.erp_asset import AssetCheck, DepreciationRecord, FixedAsset
from app.models.user import User
from app.schemas.erp_asset import (
    AssetCheckCreateIn,
    AssetCheckItemIn,
    DepreciateBatchIn,
    FixedAssetCreateIn,
    FixedAssetUpdateIn,
)
from app.services.code_generator import BizType, resolve_code


router = APIRouter()


def _asset_out(x: FixedAsset) -> dict:
    return {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "asset_no": x.asset_no,
        "name": x.name,
        "category": x.category,
        "model": x.model,
        "equipment_id": x.equipment_id,
        "workshop": x.workshop,
        "department_id": x.department_id,
        "original_value": float(x.original_value or 0),
        "residual_value": float(x.residual_value or 0),
        "useful_life_months": x.useful_life_months,
        "depreciation_method": x.depreciation_method,
        "monthly_depreciation": float(x.monthly_depreciation or 0),
        "purchase_date": str(x.purchase_date) if x.purchase_date else None,
        "start_use_date": str(x.start_use_date) if x.start_use_date else None,
        "status": x.status,
        "accumulated_depreciation": float(x.accumulated_depreciation or 0),
        "book_value": float(x.book_value or 0),
        "remark": x.remark,
        "created_at": x.created_at,
    }


def _depr_out(x: DepreciationRecord) -> dict:
    return {
        "id": x.id,
        "asset_id": x.asset_id,
        "period": x.period,
        "depreciation_amount": float(x.depreciation_amount or 0),
        "accumulated_depreciation": float(x.accumulated_depreciation or 0),
        "book_value": float(x.book_value or 0),
    }


def _check_item_out(x) -> dict:
    return {
        "id": x.id,
        "asset_id": x.asset_id,
        "expected_qty": x.expected_qty,
        "checked_qty": x.checked_qty,
        "diff_qty": x.diff_qty,
        "status": x.status,
        "remark": x.remark,
    }


def _check_out(x: AssetCheck, with_items: bool = False) -> dict:
    d = {
        "id": x.id,
        "check_no": x.check_no,
        "check_date": str(x.check_date),
        "status": x.status,
        "remark": x.remark,
        "created_by": x.created_by,
        "created_at": x.created_at,
    }
    if with_items:
        d["items"] = [_check_item_out(it) for it in x.items]
    return d


# ---------- 台账 ----------

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_asset import (
    asset_no_exists,
    check_no_exists,
    complete_check,
    count_assets,
    create_asset,
    create_check,
    create_depreciation_record,
    delete_asset,
    get_asset,
    get_check,
    get_depreciation_record,
    list_asset_depreciation,
    list_assets,
    list_checks,
    list_depreciation_records,
    update_asset,
    update_check_items,
)
from app.models.erp_asset import AssetCheck, DepreciationRecord, FixedAsset
from app.models.user import User
from app.schemas.erp_asset import (
    AssetCheckCreateIn,
    AssetCheckItemIn,
    DepreciateBatchIn,
    FixedAssetCreateIn,
    FixedAssetUpdateIn,
)
from app.services.code_generator import BizType, resolve_code


router = APIRouter()


def _asset_out(x: FixedAsset) -> dict:
    return {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "asset_no": x.asset_no,
        "name": x.name,
        "category": x.category,
        "model": x.model,
        "equipment_id": x.equipment_id,
        "workshop": x.workshop,
        "department_id": x.department_id,
        "original_value": float(x.original_value or 0),
        "residual_value": float(x.residual_value or 0),
        "useful_life_months": x.useful_life_months,
        "depreciation_method": x.depreciation_method,
        "monthly_depreciation": float(x.monthly_depreciation or 0),
        "purchase_date": str(x.purchase_date) if x.purchase_date else None,
        "start_use_date": str(x.start_use_date) if x.start_use_date else None,
        "status": x.status,
        "accumulated_depreciation": float(x.accumulated_depreciation or 0),
        "book_value": float(x.book_value or 0),
        "remark": x.remark,
        "created_at": x.created_at,
    }


def _depr_out(x: DepreciationRecord) -> dict:
    return {
        "id": x.id,
        "asset_id": x.asset_id,
        "period": x.period,
        "depreciation_amount": float(x.depreciation_amount or 0),
        "accumulated_depreciation": float(x.accumulated_depreciation or 0),
        "book_value": float(x.book_value or 0),
    }


def _check_item_out(x) -> dict:
    return {
        "id": x.id,
        "asset_id": x.asset_id,
        "expected_qty": x.expected_qty,
        "checked_qty": x.checked_qty,
        "diff_qty": x.diff_qty,
        "status": x.status,
        "remark": x.remark,
    }


def _check_out(x: AssetCheck, with_items: bool = False) -> dict:
    d = {
        "id": x.id,
        "check_no": x.check_no,
        "check_date": str(x.check_date),
        "status": x.status,
        "remark": x.remark,
        "created_by": x.created_by,
        "created_at": x.created_at,
    }
    if with_items:
        d["items"] = [_check_item_out(it) for it in x.items]
    return d


# ---------- 台账 ----------

@router.get("")
def list_assets_api(
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_assets(db, user.tenant_id, category=category, status=status, keyword=keyword, offset=offset, limit=limit)
    total = count_assets(db, user.tenant_id, category=category, status=status)
    return ok({"items": [_asset_out(x) for x in items], "total": total})



@router.post("")
def create_asset_api(
    body: FixedAssetCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset_no = resolve_code(
        db,
        tenant_id=user.tenant_id,
        biz_type=BizType.FIXED_ASSET,
        code=body.asset_no,
        exists=lambda c: asset_no_exists(db, user.tenant_id, c),
        duplicate_msg="资产编号已存在",
    )
    a = create_asset(db, user.tenant_id, {**body.model_dump(), "asset_no": asset_no}, created_by=user.id)
    db.commit()
    return ok({"id": a.id, "asset_no": a.asset_no}, "创建成功")



@router.post("/depreciate-batch")
def depreciate_batch_api(
    body: DepreciateBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assets = list_assets(db, user.tenant_id, status="active")
    created: list[int] = []
    for a in assets:
        if get_depreciation_record(db, user.tenant_id, a.id, body.period):
            continue  # 幂等
        if (a.book_value or 0) <= 0:
            continue
        amt = a.monthly_depreciation or 0
        if amt <= 0:
            continue
        rec = create_depreciation_record(db, a, body.period, amt)
        created.append(rec.id)
    db.commit()
    return ok({"created": len(created), "asset_ids": created}, "批量计提完成")



@router.get("/depreciation")
def list_depreciation_api(
    period: str | None = Query(default=None),
    asset_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_depreciation_records(db, user.tenant_id, period=period, asset_id=asset_id, offset=offset, limit=limit)
    return ok({"items": [_depr_out(x) for x in items]})



@router.get("/{asset_id}/depreciation")
def asset_depreciation_api(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_asset_depreciation(db, user.tenant_id, asset_id)
    return ok({"items": [_depr_out(x) for x in items]})


# ---------- 盘点 ----------

@router.post("/checks")
def create_check_api(
    body: AssetCheckCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    check_no = resolve_code(
        db,
        tenant_id=user.tenant_id,
        biz_type=BizType.ASSET_CHECK,
        code=body.check_no,
        exists=lambda c: check_no_exists(db, user.tenant_id, c),
        duplicate_msg="盘点单号已存在",
    )
    ck = create_check(
        db, user.tenant_id,
        check_no=check_no, check_date=body.check_date, remark=body.remark,
        items=[it.model_dump() for it in (getattr(body, "items", None) or [])],
        created_by=user.id,
    )
    db.commit()
    return ok({"id": ck.id, "check_no": ck.check_no}, "创建成功")



@router.get("/checks")
def list_checks_api(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_checks(db, user.tenant_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_check_out(x) for x in items]})



@router.get("/checks/{check_id}")
def detail_check_api(
    check_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ck = get_check(db, user.tenant_id, check_id)
    if not ck:
        raise HTTPException(status_code=404, detail="盘点单不存在")
    return ok(_check_out(ck, with_items=True))



@router.put("/checks/{check_id}")
def update_check_api(
    check_id: int,
    body: list[AssetCheckItemIn],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ck = get_check(db, user.tenant_id, check_id)
    if not ck:
        raise HTTPException(status_code=404, detail="盘点单不存在")
    if ck.status == "done":
        raise HTTPException(status_code=400, detail="已完成的盘点单不可修改")
    ck = update_check_items(db, ck, [it.model_dump() for it in body])
    db.commit()
    return ok({"id": ck.id}, "已更新")



@router.post("/checks/{check_id}/complete")
def complete_check_api(
    check_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ck = get_check(db, user.tenant_id, check_id)
    if not ck:
        raise HTTPException(status_code=404, detail="盘点单不存在")
    if ck.status == "done":
        raise HTTPException(status_code=400, detail="盘点单已完成")
    ck = complete_check(db, ck)
    db.commit()
    return ok({"id": ck.id}, "盘点完成")


@router.get("/{asset_id}")
def detail_asset_api(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = get_asset(db, user.tenant_id, asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="资产不存在")
    return ok(_asset_out(a))



@router.put("/{asset_id}")
def update_asset_api(
    asset_id: int,
    body: FixedAssetUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = get_asset(db, user.tenant_id, asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="资产不存在")
    data = body.model_dump(exclude_unset=True)
    if "asset_no" in data and asset_no_exists(db, user.tenant_id, data["asset_no"], exclude_id=a.id):
        raise HTTPException(status_code=400, detail="资产编号已存在")
    a = update_asset(db, a, data)
    db.commit()
    return ok({"id": a.id}, "已更新")



@router.delete("/{asset_id}")
def delete_asset_api(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = get_asset(db, user.tenant_id, asset_id)
    if not a:
        raise HTTPException(status_code=404, detail="资产不存在")
    if list_asset_depreciation(db, user.tenant_id, asset_id):
        raise HTTPException(status_code=400, detail="资产已有折旧记录，无法删除")
    delete_asset(db, a)
    db.commit()
    return ok(msg="已删除")


# ---------- 折旧 ----------
