from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.response import ok
from app.services.captcha import create_captcha
from app.services.login_captcha import is_login_captcha_enabled


router = APIRouter()


@router.get("")
def get_captcha_api(db: Session = Depends(get_db)):
    """获取登录验证码（所有登录入口共用）。"""
    enabled = is_login_captcha_enabled(db)
    if not enabled:
        return ok({"enabled": False})
    try:
        captcha_id, image_base64, expires_in = create_captcha()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证码生成失败，请确认已安装 Pillow：{e}")
    return ok(
        {
            "enabled": True,
            "captcha_id": captcha_id,
            "image_base64": image_base64,
            "expires_in": int(expires_in),
        }
    )
