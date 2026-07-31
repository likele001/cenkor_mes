from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.supplier import create_supplier, get_supplier_by_code, get_supplier_by_id, list_suppliers, update_supplier
from app.models.user import User
from app.schemas.supplier import SupplierCreateIn, SupplierUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["supplier.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "contact_name": x.contact_name,
        "phone": x.phone,
        "address": x.address,
        "remark": x.remark,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_suppliers(db, keyword=keyword, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_suppliers_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_suppliers(db, keyword=None, offset=0, limit=999999, include_inactive=True)
    headers = ["编码", "名称", "联系人", "电话", "地址", "状态"]
    rows = [[i.code, i.name, i.contact_name or "", i.phone or "", i.address or "", "启用" if i.is_active else "停用"] for i in items]
    return make_excel_response(headers, rows, "suppliers.xlsx", "供应商")


@router.post("")
def create_api(payload: SupplierCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    supplier_code = resolve_code(
        db,
        biz_type=BizType.SUPPLIER,
        code=payload.code,
        exists=lambda c: get_supplier_by_code(db, c) is not None,
        duplicate_msg="供应商编码已存在",
    )
    item = create_supplier(
        db,
        code=supplier_code,
        name=payload.name,
        contact_name=payload.contact_name,
        phone=payload.phone,
        address=payload.address,
        remark=payload.remark,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{supplier_id}")
def get_api(supplier_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_supplier_by_id(db, supplier_id=supplier_id)
    if not item:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return ok(_out(item))


@router.put("/{supplier_id}")
def update_api(supplier_id: int, payload: SupplierUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_supplier_by_id(db, supplier_id=supplier_id)
    if not item:
        raise HTTPException(status_code=404, detail="供应商不存在")
    if payload.code is not None:
        exists = get_supplier_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="供应商编码已存在")
    update_supplier(
        db,
        item,
        code=payload.code,
        name=payload.name,
        contact_name=payload.contact_name,
        phone=payload.phone,
        address=payload.address,
        remark=payload.remark,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{supplier_id}")
def delete_api(supplier_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_supplier_by_id(db, supplier_id=supplier_id)
    if not item:
        raise HTTPException(status_code=404, detail="供应商不存在")
    update_supplier(db, item, is_active=False)
    db.commit()
    return ok()
