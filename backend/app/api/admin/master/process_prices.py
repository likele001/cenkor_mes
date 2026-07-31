from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.process import get_process_by_id, list_processes
from app.crud.process_price import (
    batch_upsert_prices,
    create_price,
    get_price_by_id,
    get_price_by_sku_process,
    list_prices,
    list_prices_for_sku,
    update_price,
)
from app.crud.process_route import get_default_route_for_product
from app.crud.sku import get_sku_by_id
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.sku import Sku
from app.models.user import User
from app.schemas.process_price import ProcessPriceBatchIn, ProcessPriceCreateIn, ProcessPriceUpdateIn
from app.services.display_label import process_display_name, product_display_name, sku_option_extra_fields
from app.services.entity_refs import product_ref_dict
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["price.manage"]))])


def _out(x: ProcessPrice) -> dict:
    return {
        "id": x.id,
        "sku_id": x.sku_id,
        "process_id": x.process_id,
        "unit_price": x.unit_price,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _out_list(items: list[ProcessPrice], db: Session) -> list[dict]:
    if not items:
        return []
    sku_ids = {x.sku_id for x in items}
    process_ids = {x.process_id for x in items}
    skus = db.scalars(
        select(Sku).where(Sku.id.in_(sku_ids)).options(selectinload(Sku.product))
    ).all()
    processes = db.scalars(select(Process).where(Process.id.in_(process_ids))).all()
    sku_map = {s.id: s for s in skus}
    proc_map = {p.id: p for p in processes}
    result = []
    for x in items:
        row = _out(x)
        sku = sku_map.get(x.sku_id)
        proc = proc_map.get(x.process_id)
        product = sku.product if sku else None
        if sku:
            extra = sku_option_extra_fields(
                product_name=product.name if product else None,
                product_description=product.description if product else None,
                product_code=product.code if product else None,
                product_category=product.category if product else None,
                sku_name=sku.name,
                sku_code=sku.code,
                sku_color=sku.color,
                sku_material=sku.material,
                sku_spec=sku.spec,
            )
            row["sku"] = {
                "id": sku.id,
                "code": sku.code,
                "name": sku.name,
                "display_name": extra["sku_display_name"],
                "display_label": extra["display_label"],
                "product_id": sku.product_id,
                "product_name": extra["product_name"],
            }
        else:
            row["sku"] = None
        if product:
            row["product"] = {
                "id": product.id,
                "code": product.code,
                "name": product.name,
                "display_name": product_display_name(product.name, product.description, product.code, product.category),
            }
        else:
            row["product"] = None
        if proc:
            row["process"] = {
                "id": proc.id,
                "code": proc.code,
                "name": proc.name,
                "display_name": process_display_name(proc.name, proc.code),
            }
        else:
            row["process"] = None
        result.append(row)
    return result


@router.get("")
def list_api(
    sku_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if sku_id is not None:
        sku = get_sku_by_id(db, sku_id=sku_id)
        if not sku:
            raise HTTPException(status_code=400, detail="产品型号不存在")
    items = list_prices(db, sku_id=sku_id, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": _out_list(items, db)})


@router.get("/export")
def export_process_prices_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_prices(db, sku_id=None, offset=0, limit=999999, include_inactive=True)
    headers = ["型号编码", "型号名称", "工序名称", "工价", "创建时间"]
    rows = []
    for i in items:
        sku = getattr(i, "sku", None)
        proc = getattr(i, "process", None)
        rows.append([sku.code if sku else "", sku.name if sku else "", proc.name if proc else "", str(i.unit_price), str(i.created_at)])
    return make_excel_response(headers, rows, "process_prices.xlsx", "工序工价")


@router.get("/matrix")
def price_matrix_api(
    sku_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """某型号的工序工价矩阵（优先产品默认工艺路线工序，可增行补其它工序）。"""
    sku = get_sku_by_id(db, sku_id=sku_id)
    if not sku:
        raise HTTPException(status_code=400, detail="产品型号不存在")
    product = sku.product if hasattr(sku, "product") else None
    if not product:
        from app.models.product import Product

        product = db.get(Product, sku.product_id)

    existing = {p.process_id: p for p in list_prices_for_sku(db, sku_id)}
    process_rows: list[Process] = []
    route_name: str | None = None
    route_source = "all"

    try:
        route = get_default_route_for_product(db, sku.product_id)
        route_name = route.name
        route_source = "default_route"
        proc_ids = [s.process_id for s in sorted(route.steps, key=lambda x: x.seq)]
        if proc_ids:
            proc_map = {
                p.id: p
                for p in db.scalars(
                    select(Process).where(Process.id.in_(proc_ids))
                ).all()
            }
            process_rows = [proc_map[pid] for pid in proc_ids if pid in proc_map]
    except ValueError:
        process_rows = list_processes(db, offset=0, limit=500, include_inactive=False)

    seen = {p.id for p in process_rows}
    for pid, price in existing.items():
        if pid not in seen:
            proc = db.get(Process, pid)
            if proc:
                process_rows.append(proc)
                seen.add(pid)

    rows = []
    for proc in process_rows:
        ex = existing.get(proc.id)
        rows.append(
            {
                "process_id": proc.id,
                "process_code": proc.code,
                "process_name": proc.name,
                "process_display_name": process_display_name(proc.name, proc.code),
                "price_id": ex.id if ex else None,
                "unit_price": float(ex.unit_price) if ex else None,
                "is_active": ex.is_active if ex else True,
            }
        )

    sku_extra = None
    if sku:
        extra = sku_option_extra_fields(
            product_name=product.name if product else None,
            product_description=product.description if product else None,
            product_code=product.code if product else None,
            product_category=product.category if product else None,
            sku_name=sku.name,
            sku_code=sku.code,
            sku_color=sku.color,
            sku_material=sku.material,
            sku_spec=sku.spec,
        )
        sku_extra = {
            "id": sku.id,
            "code": sku.code,
            "name": sku.name,
            "display_label": extra["display_label"],
            "product_id": sku.product_id,
        }

    return ok(
        {
            "sku": sku_extra,
            "product": product_ref_dict(product) if product else None,
            "route_name": route_name,
            "route_source": route_source,
            "rows": rows,
        }
    )


@router.post("/batch")
def batch_save_api(payload: ProcessPriceBatchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sku = get_sku_by_id(db, sku_id=payload.sku_id)
    if not sku:
        raise HTTPException(status_code=400, detail="产品型号不存在")
    seen_proc: set[int] = set()
    for it in payload.items:
        if it.process_id in seen_proc:
            raise HTTPException(status_code=400, detail=f"工序#{it.process_id} 重复")
        seen_proc.add(it.process_id)
        proc = get_process_by_id(db, process_id=it.process_id)
        if not proc:
            raise HTTPException(status_code=400, detail=f"工序#{it.process_id} 不存在")
    try:
        created, updated = batch_upsert_prices(
            db,
            payload.sku_id,
            [it.model_dump() for it in payload.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return ok({"created": created, "updated": updated, "sku_id": payload.sku_id})


@router.post("")
def create_api(payload: ProcessPriceCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sku = get_sku_by_id(db, sku_id=payload.sku_id)
    if not sku:
        raise HTTPException(status_code=400, detail="产品型号不存在")
    process = get_process_by_id(db, process_id=payload.process_id)
    if not process:
        raise HTTPException(status_code=400, detail="工序不存在")
    exists = get_price_by_sku_process(db, sku_id=payload.sku_id, process_id=payload.process_id)
    if exists:
        raise HTTPException(status_code=400, detail="该型号与工序的工价已存在")
    item = create_price(
        db,
        sku_id=payload.sku_id,
        process_id=payload.process_id,
        unit_price=payload.unit_price,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{price_id}")
def get_api(price_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_price_by_id(db, price_id=price_id)
    if not item:
        raise HTTPException(status_code=404, detail="工价不存在")
    return ok(_out(item))


@router.put("/{price_id}")
def update_api(price_id: int, payload: ProcessPriceUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_price_by_id(db, price_id=price_id)
    if not item:
        raise HTTPException(status_code=404, detail="工价不存在")
    update_price(db, item, unit_price=payload.unit_price, is_active=payload.is_active)
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{price_id}")
def delete_api(price_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_price_by_id(db, price_id=price_id)
    if not item:
        raise HTTPException(status_code=404, detail="工价不存在")
    update_price(db, item, is_active=False)
    db.commit()
    return ok()
