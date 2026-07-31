from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.services.wechat_miniapp_settings import get_wechat_miniapp_settings_admin, save_wechat_miniapp_settings

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])

class WechatMiniappIn(BaseModel):
    app_id: str = ""
    app_secret: str | None = None

@router.get("/wechat-miniapp")
def get_api(db=Depends(get_db), user=Depends(get_current_user)):
    return ok(get_wechat_miniapp_settings_admin(db, user.tenant_id))

@router.put("/wechat-miniapp")
def put_api(payload: WechatMiniappIn, db=Depends(get_db), user=Depends(get_current_user)):
    data = save_wechat_miniapp_settings(db, tenant_id=user.tenant_id, payload=payload.model_dump())
    return ok(data)
