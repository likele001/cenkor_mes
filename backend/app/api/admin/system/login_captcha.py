# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""独立版登录验证码开关。

LightMes 的开关挂在平台总控 `app/api/platform/settings.py`。独立版移除整套
平台总控后该入口一并消失，`login_captcha_enabled` 只能回退 DEFAULTS["false"]，
后台没有任何途径打开验证码。本模块在管理端补一个轻量入口，读写的仍是同一张
`platform_settings` 表，因此 public-config / captcha / auth 三条既有读取链路
无需任何改动，也不依赖多租户 / SaaS 概念。

写入走 ORM `set_setting()` + `db.commit()`，会触发 core/business_cache.py 中
PlatformSetting -> NS_PUBLIC_CONFIG 的版本 bump，public-config 读缓存即时失效；
`/api/auth/captcha` 本来就不缓存，开关立即生效。
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.platform_setting import set_setting
from app.models.user import User
from app.services.login_captcha import SETTING_KEY, is_login_captcha_enabled

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


class LoginCaptchaSettingsIn(BaseModel):
    enabled: bool


@router.get("")
def get_login_captcha_settings_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前开关值；DB 无记录时返回 DEFAULTS 的 false。"""
    return ok({"enabled": is_login_captcha_enabled(db)})


@router.put("")
def save_login_captcha_settings_api(
    payload: LoginCaptchaSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    set_setting(db, SETTING_KEY, "true" if payload.enabled else "false")
    write_op_log(
        db,
        request,
        user,
        module="system.setting",
        action="update",
        object_type="platform_setting",
        object_id=None,
        detail=f"{SETTING_KEY}={str(payload.enabled).lower()}",
    )
    db.commit()
    return ok({"enabled": payload.enabled})
