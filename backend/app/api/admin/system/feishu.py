from fastapi import APIRouter, Depends
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])

@router.get("/feishu")
def get_settings_api(db=Depends(get_db), user=Depends(get_current_user)):
    return ok({})

@router.put("/feishu")
def put_settings_api(db=Depends(get_db), user=Depends(get_current_user)):
    return ok({})
