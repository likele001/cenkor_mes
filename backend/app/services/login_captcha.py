"""登录类接口的验证码开关与校验。"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.platform_setting import get_bool_setting
from app.services.captcha import verify_captcha

SETTING_KEY = "login_captcha_enabled"


def is_login_captcha_enabled(db: Session) -> bool:
    return get_bool_setting(db, SETTING_KEY)


def assert_login_captcha(db: Session, captcha_id: str | None, captcha_code: str | None) -> None:
    if not is_login_captcha_enabled(db):
        return
    if not captcha_id or not captcha_code:
        raise HTTPException(status_code=400, detail="请输入验证码")
    if not verify_captcha(captcha_id, captcha_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
