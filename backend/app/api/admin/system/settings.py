import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.tenant_setting import delete_setting, get_setting, list_settings, upsert_setting
from app.models.user import User
from app.schemas.tenant_setting import TenantSettingUpsertIn


router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


def _value_out(v: str | None):
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return v


def _out(x) -> dict:
    return {"id": x.id, "key": x.key, "value": _value_out(x.value), "updated_at": x.updated_at}


@router.get("")
def list_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_settings(db, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/{key}")
def get_api(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_setting(db, key=key)
    if not item:
        return ok(None)
    return ok(_out(item))


@router.put("/{key}")
def upsert_api(
    key: str,
    payload: TenantSettingUpsertIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = payload.value
    if v is None:
        s = None
    elif isinstance(v, str):
        s = v
    else:
        s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    item = upsert_setting(db, key=key, value=s)
    write_op_log(
        db,
        request,
        user,
        module="system.setting",
        action="upsert",
        object_type="tenant_setting",
        object_id=item.id,
        detail=f"{item.key}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{key}")
def delete_api(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_setting(db, key=key)
    if not item:
        return ok()
    write_op_log(
        db,
        request,
        user,
        module="system.setting",
        action="delete",
        object_type="tenant_setting",
        object_id=item.id,
        detail=f"{item.key}",
    )
    delete_setting(db, item)
    db.commit()
    return ok()
