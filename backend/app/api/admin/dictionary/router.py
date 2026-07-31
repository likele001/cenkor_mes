from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.dictionary import (
    create_dict_item,
    create_dict_type,
    delete_dict_item,
    get_dict_item_by_id,
    get_dict_type_by_id,
    list_dict_items,
    list_dict_types,
)
from app.schemas.dictionary import DictItemCreateIn, DictTypeCreateIn
from app.models.user import User

router = APIRouter(dependencies=[Depends(require_permissions(["dict.manage"]))])


@router.get("/types")
def list_types_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = list_dict_types(db)
    return ok({"items": [{"id": t.id, "code": t.code, "name": t.name, "is_active": t.is_active} for t in items]})


@router.post("/types")
def create_type_api(body: DictTypeCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = create_dict_type(db, code=body.code, name=body.name)
    db.commit()
    return ok({"id": t.id, "code": t.code})


@router.get("/types/{dict_type_id}/items")
def list_items_api(dict_type_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = list_dict_items(db, dict_type_id=dict_type_id)
    return ok({"items": [{"id": i.id, "label": i.label, "value": i.value, "sort_order": i.sort_order, "is_active": i.is_active} for i in items]})


@router.post("/types/{dict_type_id}/items")
def create_item_api(
    dict_type_id: int,
    body: DictItemCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    i = create_dict_item(
        db,
        dict_type_id=dict_type_id,
        label=body.label,
        value=body.value,
        sort_order=body.sort_order,
    )
    db.commit()
    return ok({"id": i.id, "label": i.label, "value": i.value})


@router.delete("/types/{dict_type_id}/items/{item_id}")
def delete_item_api(
    dict_type_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dt = get_dict_type_by_id(db, dict_type_id=dict_type_id)
    if not dt:
        raise HTTPException(status_code=404, detail="字典类型不存在")
    item = get_dict_item_by_id(db, dict_type_id=dict_type_id, item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    delete_dict_item(db, item)
    db.commit()
    return ok({"deleted": True})
