from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.process_route import create_route, get_route_by_id, list_routes, update_route
from app.crud.product import get_product_by_id
from app.models.process import Process
from app.models.user import User
from app.schemas.process_route import ProcessRouteCreateIn, ProcessRouteUpdateIn


router = APIRouter(dependencies=[Depends(require_permissions(["product.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "product_id": x.product_id,
        "name": x.name,
        "is_default": x.is_default,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "steps": [
            {
                "id": s.id,
                "route_id": s.route_id,
                "seq": s.seq,
                "process_id": s.process_id,
            }
            for s in (x.steps or [])
        ],
    }


def _validate_steps(db: Session, steps) -> list[tuple[int, int]]:
    pairs = [(s.seq, s.process_id) for s in steps]
    if len({seq for seq, _ in pairs}) != len(pairs):
        raise HTTPException(status_code=400, detail="工艺路线步骤序号重复")
    process_ids = {pid for _, pid in pairs}
    if process_ids:
        found = set(
            db.scalars(select(Process.id).where(Process.id.in_(list(process_ids)))).all()
        )
        if found != process_ids:
            raise HTTPException(status_code=400, detail="工艺路线步骤包含不存在的工序")
    return pairs


@router.get("")
def list_api(
    product_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if product_id is not None:
        product = get_product_by_id(db, product_id=product_id)
        if not product:
            raise HTTPException(status_code=400, detail="产品不存在")
    items = list_routes(db, product_id=product_id, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": [_out(x) for x in items]})


@router.post("")
def create_api(payload: ProcessRouteCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = get_product_by_id(db, product_id=payload.product_id)
    if not product:
        raise HTTPException(status_code=400, detail="产品不存在")
    steps = _validate_steps(db, steps=payload.steps)
    item = create_route(
        db,
        product_id=payload.product_id,
        name=payload.name,
        is_default=payload.is_default,
        is_active=payload.is_active,
        steps=steps,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{route_id}")
def get_api(route_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_route_by_id(db, route_id=route_id)
    if not item:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    return ok(_out(item))


@router.put("/{route_id}")
def update_api(route_id: int, payload: ProcessRouteUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_route_by_id(db, route_id=route_id)
    if not item:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    steps = None
    if payload.steps is not None:
        steps = _validate_steps(db, steps=payload.steps)
    update_route(db, item, name=payload.name, is_default=payload.is_default, is_active=payload.is_active, steps=steps)
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{route_id}")
def delete_api(route_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_route_by_id(db, route_id=route_id)
    if not item:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    update_route(db, item, is_active=False)
    db.commit()
    return ok()
