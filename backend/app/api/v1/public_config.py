# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""免登录的公开配置：登录页与前端品牌区要用，必须在拿到 token 之前可读。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.core.response import ok
from app.crud.attachment import get_attachment_by_id
from app.services.attachment_media import attachment_play_url
from app.services.company_settings import get_company_info, get_logo_attachment_id
from app.services.login_captcha import is_login_captcha_enabled
from app.storage.factory import get_storage_for

router = APIRouter()


@router.get("")
def public_config_api(db: Session = Depends(get_db)):
    info = get_company_info(db)
    return ok({
        "company_name": info["name"],
        "logo_url": info["logo_url"],
        "login_captcha_enabled": is_login_captcha_enabled(db),
        "session_expire_minutes": int(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "remember_me_expire_minutes": int(settings.REMEMBER_ME_EXPIRE_MINUTES),
    })


@router.get("/logo")
def public_logo_api(db: Session = Depends(get_db)):
    """只输出 company.logo 里记录的那个附件 ID，不接受任何外部入参。"""
    logo_id = get_logo_attachment_id(db)
    if not logo_id:
        raise HTTPException(status_code=404, detail="未设置 logo")
    att = get_attachment_by_id(db, attachment_id=logo_id)
    if not att or not (att.content_type or "").startswith("image/"):
        raise HTTPException(status_code=404, detail="logo 不存在")

    storage = get_storage_for(att.storage_driver, db)
    if storage.driver != "local":
        return RedirectResponse(attachment_play_url(att, db=db), status_code=302)

    path = storage.resolve_path(key=att.storage_key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="logo 文件不存在")
    return FileResponse(
        path,
        media_type=att.content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )
