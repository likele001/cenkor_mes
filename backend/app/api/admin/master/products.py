from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.product import create_product, get_product_by_code, get_product_by_id, list_products, update_product
from app.models.user import User
from app.schemas.product import ProductCreateIn, ProductUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.services.display_label import product_display_name
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["product.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "display_name": product_display_name(x.name, x.description, x.code, x.category),
        "category": x.category,
        "unit": x.unit,
        "description": x.description,
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
    items = list_products(db, keyword=keyword, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_products_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_products(db, keyword=None, offset=0, limit=999999, include_inactive=True)
    headers = ["编码", "名称", "分类", "单位", "描述", "状态"]
    rows = [[i.code, i.name, i.category or "", i.unit or "", i.description or "", "启用" if i.is_active else "停用"] for i in items]
    return make_excel_response(headers, rows, "products.xlsx", "产品")


@router.post("")
def create_api(payload: ProductCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product_code = resolve_code(
        db,
        biz_type=BizType.PRODUCT,
        code=payload.code,
        exists=lambda c: get_product_by_code(db, c) is not None,
        duplicate_msg="产品编码已存在",
    )
    item = create_product(
        db,
        code=product_code,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{product_id}")
def get_api(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_product_by_id(db, product_id=product_id)
    if not item:
        raise HTTPException(status_code=404, detail="产品不存在")
    return ok(_out(item))


@router.put("/{product_id}")
def update_api(product_id: int, payload: ProductUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_product_by_id(db, product_id=product_id)
    if not item:
        raise HTTPException(status_code=404, detail="产品不存在")
    if payload.code is not None:
        exists = get_product_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="产品编码已存在")
    update_product(
        db,
        item,
        code=payload.code,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{product_id}")
def delete_api(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_product_by_id(db, product_id=product_id)
    if not item:
        raise HTTPException(status_code=404, detail="产品不存在")
    update_product(db, item, is_active=False)
    db.commit()
    return ok()
