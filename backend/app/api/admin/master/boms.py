from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.material import get_material_by_id
from app.crud.material_bom import (
    BOM_SCOPE_GLOBAL,
    BOM_SCOPE_PRODUCT,
    BOM_SCOPE_SKU,
    copy_bom_to_sku,
    create_bom,
    get_bom_by_id,
    get_effective_bom_for_sku,
    get_sku_bom,
    list_boms,
    update_bom,
)
from app.crud.product import get_product_by_id, list_products
from app.crud.sku import get_sku_by_id, list_skus
from app.models.product import Product
from app.models.user import User
from app.schemas.material_bom import MaterialBomCopyToSkuIn, MaterialBomCreateIn, MaterialBomUpdateIn
from app.services.display_label import product_display_name, sku_option_extra_fields
from app.services.sku_scope import is_material_product
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["bom.manage"]))])

SCOPE_LABELS = {
    BOM_SCOPE_SKU: "型号专属",
    BOM_SCOPE_PRODUCT: "产品默认",
    BOM_SCOPE_GLOBAL: "全厂默认",
}


def _list_out(bom) -> dict:
    """列表接口：不加载明细，避免 N+1 与 lazy load 异常。"""
    sku = getattr(bom, "sku", None)
    product = getattr(bom, "product", None)
    scope = getattr(bom, "scope", None) or BOM_SCOPE_SKU
    return {
        "id": bom.id,
        "scope": scope,
        "scope_label": SCOPE_LABELS.get(scope, scope),
        "sku_id": bom.sku_id,
        "product_id": getattr(bom, "product_id", None),
        "sku_code": sku.code if sku else None,
        "sku_name": sku.name if sku else None,
        "product_code": product.code if product else None,
        "product_name": product.name if product else None,
        "name": getattr(bom, "name", None),
        "version": bom.version,
        "remark": bom.remark,
        "is_default": bool(getattr(bom, "is_default", False)),
        "is_active": bom.is_active,
        "created_by": bom.created_by,
        "created_at": bom.created_at,
        "updated_at": bom.updated_at,
        "items": [],
    }


def _out(bom) -> dict:
    sku = getattr(bom, "sku", None)
    product = getattr(bom, "product", None)
    return {
        "id": bom.id,
        "scope": getattr(bom, "scope", BOM_SCOPE_SKU),
        "scope_label": SCOPE_LABELS.get(getattr(bom, "scope", BOM_SCOPE_SKU), getattr(bom, "scope", BOM_SCOPE_SKU)),
        "sku_id": bom.sku_id,
        "product_id": getattr(bom, "product_id", None),
        "sku_code": sku.code if sku else None,
        "sku_name": sku.name if sku else None,
        "product_code": product.code if product else None,
        "product_name": product.name if product else None,
        "name": getattr(bom, "name", None),
        "version": bom.version,
        "remark": bom.remark,
        "is_default": bool(getattr(bom, "is_default", False)),
        "is_active": bom.is_active,
        "created_by": bom.created_by,
        "created_at": bom.created_at,
        "updated_at": bom.updated_at,
        "items": [
            {
                "id": it.id,
                "material_id": it.material_id,
                "material_code": it.material.code if it.material else None,
                "material_name": it.material.name if it.material else None,
                "qty_per": it.qty_per,
                "remark": it.remark,
            }
            for it in (bom.items or [])
        ],
    }


def _raise_bom_db_error(exc: Exception) -> None:
    raw = str(getattr(exc, "orig", exc))
    if any(k in raw for k in ("scope", "product_id", "is_default", "Unknown column", "no such column")):
        raise HTTPException(
            status_code=400,
            detail="BOM 表结构未升级，请在服务器执行：cd backend && alembic upgrade head（需包含 0033_bom_scope）",
        ) from exc
    raise HTTPException(status_code=500, detail=f"BOM 查询失败：{raw[:300]}") from exc


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    sku_id: int | None = Query(default=None, ge=1),
    product_id: int | None = Query(default=None, ge=1),
    scope: str | None = Query(default=None, description="sku|product|global"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        items = list_boms(
            db,
            keyword=keyword,
            sku_id=sku_id,
            product_id=product_id,
            scope=scope,
            offset=offset,
            limit=limit,
        )
    except (OperationalError, ProgrammingError) as e:
        _raise_bom_db_error(e)
    return ok({"items": [_list_out(x) for x in items]})


@router.get("/export")
def export_boms_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_boms(db, keyword=None, sku_id=None, product_id=None, scope=None, offset=0, limit=999999)
    headers = ["名称", "产品名称", "版本", "状态", "备注"]
    rows = []
    for i in items:
        p = getattr(i, "product", None)
        sku = getattr(i, "sku", None)
        name = i.name or (sku.name if sku else "")
        product_name = p.name if p else ""
        rows.append([name, product_name, str(i.version), "启用" if i.is_active else "停用", i.remark or ""])
    return make_excel_response(headers, rows, "boms.xlsx", "BOM")


@router.get("/meta/form-options")
def form_options_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """BOM 页型号下拉：带产品展示名，仅成品型号。"""
    skus = list_skus(
        db,
        product_id=None,
        keyword=None,
        offset=0,
        limit=200,
        include_inactive=False,
        finished_products_only=True,
    )
    product_ids = {s.product_id for s in skus}
    product_map: dict[int, Product] = {}
    if product_ids:
        products = db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
        product_map = {p.id: p for p in products}
    sku_options = []
    for s in skus:
        p = product_map.get(s.product_id)
        extra = sku_option_extra_fields(
            product_name=p.name if p else None,
            product_description=p.description if p else None,
            product_code=p.code if p else None,
            product_category=p.category if p else None,
            sku_name=s.name,
            sku_code=s.code,
            sku_color=s.color,
            sku_material=s.material,
            sku_spec=s.spec,
        )
        sku_options.append(
            {
                "id": s.id,
                "product_id": s.product_id,
                "code": s.code,
                "name": s.name,
                "color": s.color,
                "material": s.material,
                "spec": s.spec,
                **extra,
            }
        )
    products = list_products(
        db, keyword=None, offset=0, limit=200, include_inactive=False
    )
    product_options = []
    for p in products:
        if is_material_product(p):
            continue
        product_options.append(
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "display_name": product_display_name(
                    p.name, p.description, p.code, p.category
                ),
            }
        )
    return ok({"skus": sku_options, "products": product_options})


@router.get("/resolve/{sku_id}")
def resolve_for_sku_api(sku_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """查看某型号最终生效的 BOM 及来源（sku/product/global）。"""
    bom, source = get_effective_bom_for_sku(db, sku_id=sku_id)
    if not bom:
        return ok({"sku_id": sku_id, "source": "none", "bom": None})
    bom2 = get_bom_by_id(db, bom_id=bom.id)
    return ok({"sku_id": sku_id, "source": source, "bom": _out(bom2) if bom2 else None})


@router.post("")
def create_api(payload: MaterialBomCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.scope == BOM_SCOPE_SKU:
        sku = get_sku_by_id(db, sku_id=payload.sku_id or 0)
        if not sku:
            raise HTTPException(status_code=400, detail="产品型号不存在")
    elif payload.scope == BOM_SCOPE_PRODUCT:
        p = get_product_by_id(db, product_id=payload.product_id or 0)
        if not p:
            raise HTTPException(status_code=400, detail="产品不存在")
    items_in = []
    for it in payload.items:
        m = get_material_by_id(db, material_id=it.material_id)
        if not m or not m.is_active:
            raise HTTPException(status_code=400, detail="物料不存在")
        items_in.append((it.material_id, it.qty_per, it.remark))
    try:
        bom = create_bom(
            db,
            scope=payload.scope,
            sku_id=payload.sku_id,
            product_id=payload.product_id,
            name=payload.name,
            version=payload.version,
            remark=payload.remark,
            is_default=payload.is_default,
            created_by=user.id,
            items=items_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    bom2 = get_bom_by_id(db, bom_id=bom.id)
    if not bom2:
        raise HTTPException(status_code=500, detail="创建失败")
    return ok(_out(bom2))


@router.get("/{bom_id}")
def get_api(bom_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_bom_by_id(db, bom_id=bom_id)
    if not item:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    return ok(_out(item))


@router.put("/{bom_id}")
def update_api(bom_id: int, payload: MaterialBomUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_bom_by_id(db, bom_id=bom_id)
    if not item:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    items_in = None
    if payload.items is not None:
        items_in = []
        for it in payload.items:
            m = get_material_by_id(db, material_id=it.material_id)
            if not m or not m.is_active:
                raise HTTPException(status_code=400, detail="物料不存在")
            items_in.append((it.material_id, it.qty_per, it.remark))
    update_bom(
        db,
        item,
        version=payload.version,
        remark=payload.remark,
        name=payload.name,
        is_active=payload.is_active,
        is_default=payload.is_default,
        items=items_in,
    )
    db.commit()
    item2 = get_bom_by_id(db, bom_id=bom_id)
    if not item2:
        raise HTTPException(status_code=500, detail="更新失败")
    return ok(_out(item2))


@router.post("/{bom_id}/copy-to-sku")
def copy_to_sku_api(
    bom_id: int,
    payload: MaterialBomCopyToSkuIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """将产品默认/全厂默认 BOM 复制为某型号专属 BOM（个别型号用料不同时用）。"""
    source = get_bom_by_id(db, bom_id=bom_id)
    if not source or not source.is_active:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    if source.scope == BOM_SCOPE_SKU:
        raise HTTPException(status_code=400, detail="已是型号专属 BOM，请直接编辑")
    try:
        bom = copy_bom_to_sku(db, source_bom=source, target_sku_id=payload.sku_id, created_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    bom2 = get_bom_by_id(db, bom_id=bom.id)
    return ok(_out(bom2))


@router.delete("/{bom_id}")
def delete_api(bom_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_bom_by_id(db, bom_id=bom_id)
    if not item:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    update_bom(db, item, is_active=False)
    db.commit()
    return ok()
