from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.material import create_material, get_material_by_code, get_material_by_id, list_materials, update_material
from app.crud.supplier import get_supplier_by_id
from app.models.user import User
from app.schemas.material import MaterialCreateIn, MaterialUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["material.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "unit": x.unit,
        "spec": x.spec,
        "remark": x.remark,
        "supplier_id": x.supplier_id,
        "sku_id": x.sku_id,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    supplier_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_materials(
        db,
        keyword=keyword,
        supplier_id=supplier_id,
        offset=offset,
        limit=limit,
        include_inactive=include_inactive,
    )
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_materials_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_materials(db, keyword=None, supplier_id=None, offset=0, limit=999999, include_inactive=True)
    headers = ["编码", "名称", "规格", "单位", "默认供应商", "最低库存"]
    rows = [[i.code, i.name, i.spec or "", i.unit or "", i.supplier.name if i.supplier else "", ""] for i in items]
    return make_excel_response(headers, rows, "materials.xlsx", "物料")


@router.post("")
def create_api(payload: MaterialCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    material_code = resolve_code(
        db,
        biz_type=BizType.MATERIAL,
        code=payload.code,
        exists=lambda c: get_material_by_code(db, c) is not None,
        duplicate_msg="物料编码已存在",
    )
    if payload.supplier_id is not None:
        sup = get_supplier_by_id(db, supplier_id=payload.supplier_id)
        if not sup:
            raise HTTPException(status_code=400, detail="供应商不存在")
    try:
        item = create_material(
            db,
            code=material_code,
            name=payload.name,
            unit=payload.unit,
            spec=payload.spec,
            remark=payload.remark,
            supplier_id=payload.supplier_id,
            is_active=payload.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{material_id}")
def get_api(material_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_material_by_id(db, material_id=material_id)
    if not item:
        raise HTTPException(status_code=404, detail="物料不存在")
    return ok(_out(item))


@router.put("/{material_id}")
def update_api(material_id: int, payload: MaterialUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_material_by_id(db, material_id=material_id)
    if not item:
        raise HTTPException(status_code=404, detail="物料不存在")
    if payload.code is not None:
        exists = get_material_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="物料编码已存在")
    if payload.supplier_id is not None:
        sup = get_supplier_by_id(db, supplier_id=payload.supplier_id)
        if not sup:
            raise HTTPException(status_code=400, detail="供应商不存在")
    try:
        update_material(
            db,
            item,
            code=payload.code,
            name=payload.name,
            unit=payload.unit,
            spec=payload.spec,
            remark=payload.remark,
            supplier_id=payload.supplier_id,
            is_active=payload.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{material_id}")
def delete_api(material_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_material_by_id(db, material_id=material_id)
    if not item:
        raise HTTPException(status_code=404, detail="物料不存在")
    update_material(db, item, is_active=False)
    db.commit()
    return ok()
