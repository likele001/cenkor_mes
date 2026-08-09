"""系统版本信息 / 开发日志 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.system_version import get_latest_version, list_versions
from app.models.user import User
from app.schemas.system_version import SystemVersionOut

router = APIRouter(tags=["admin-system-version"])


def _get_edition() -> str:
    try:
        from app.core.edition import EDITION
        return EDITION
    except ImportError:
        return "community"


@router.get("/version")
def get_version_info(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取当前系统版本信息。"""
    latest = get_latest_version(db)
    info = None
    if latest:
        info = SystemVersionOut.model_validate(latest).model_dump()
    return ok({
        "version": info,
        "edition": _get_edition(),
    })


@router.get("/version/history")
def list_changelog(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取所有历史版本记录（开发日志）。"""
    items = list_versions(db, offset=offset, limit=limit)
    return ok({"items": [SystemVersionOut.model_validate(x) for x in items]})