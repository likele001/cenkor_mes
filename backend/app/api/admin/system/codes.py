from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models.user import User
from app.services.code_generator import list_biz_types, preview_next_code


router = APIRouter()


@router.get("/types")
def list_types_api():
    return ok({"items": list_biz_types()})


@router.get("/next")
def next_code_api(
    biz_type: str = Query(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        code = preview_next_code(db, biz_type=biz_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"code": code, "biz_type": biz_type})
