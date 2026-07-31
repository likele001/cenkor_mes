"""微信小程序登录路由（单用户版：固定 tenant_id=1）"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.response import ok
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.services.wechat_miniapp_settings import get_wechat_miniapp_credentials

router = APIRouter()


class BindOpenidIn(BaseModel):
    username: str
    password: str
    openid: str


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "tenant_id": user.tenant_id,
        "roles": [r.code for r in user.roles] if hasattr(user, "roles") and user.roles else [],
    }


def _exchange_code(db: Session, tenant_id: int, code: str) -> str:
    app_id, secret = get_wechat_miniapp_credentials(db, tenant_id)
    if not app_id or not secret:
        raise HTTPException(
            status_code=500,
            detail="未配置微信小程序：请在管理端【系统设置-微信小程序】填写 AppID/AppSecret，或配置环境变量",
        )
    resp = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": app_id,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        errmsg = data.get("errmsg", "微信登录失败")
        raise HTTPException(status_code=400, detail=f"微信登录失败: {errmsg}")
    return openid


@router.post("/login")
def miniapp_login(
    code: str = Query(min_length=1),
    db: Session = Depends(get_db),
):
    """单用户版：固定使用 tenant_id=1 的凭据换 openid，无需传租户编码。"""
    openid = _exchange_code(db, 1, code)

    user = db.scalar(select(User).where(User.wx_miniapp_openid == openid))
    if not user:
        return ok({"openid": openid, "need_bind": True})

    token = create_access_token(payload={"sub": str(user.id), "tenant_id": user.tenant_id})
    return ok({
        "token": token,
        "access_token": token,
        "need_bind": False,
        "user": _user_payload(user),
    })


@router.post("/bind-openid")
def bind_openid(body: BindOpenidIn, db: Session = Depends(get_db)):
    """将微信 openid 绑定到系统用户（单用户版，无租户概念）。"""
    user = db.scalar(
        select(User).where(User.username == body.username),
    )
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="账号或密码错误")

    existing = db.scalar(select(User).where(User.wx_miniapp_openid == body.openid))
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="该微信已绑定其他账号")

    user.wx_miniapp_openid = body.openid
    db.commit()

    token = create_access_token(payload={"sub": str(user.id), "tenant_id": user.tenant_id})
    return ok({
        "token": token,
        "access_token": token,
        "user": _user_payload(user),
    })
