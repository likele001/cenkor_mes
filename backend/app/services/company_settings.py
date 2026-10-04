# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""企业信息设置（企业名/电话/地址/logo），存 tenant_settings 的 company.* 键。

logo 以附件 ID 形式保存，实际字节走免登录的 /api/public-config/logo 输出，
因为登录页是匿名访问的，不能依赖需要鉴权的 /api/files/{id}。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.attachment import get_attachment_by_id
from app.crud.tenant_setting import get_setting, upsert_setting

KEY_NAME = "company.name"
KEY_PHONE = "company.phone"
KEY_ADDRESS = "company.address"
KEY_LOGO = "company.logo"

LOGO_PATH = "/api/public-config/logo"

MAX_LEN = {"name": 128, "phone": 32, "address": 256}


def _read(db: Session, key: str) -> str:
    row = get_setting(db, key)
    return (row.value or "").strip() if row else ""


def _read_logo_attachment_id(db: Session) -> int | None:
    raw = _read(db, KEY_LOGO)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_company_info(db: Session) -> dict:
    logo_id = _read_logo_attachment_id(db)
    has_logo = False
    if logo_id:
        att = get_attachment_by_id(db, attachment_id=logo_id)
        has_logo = bool(att and (att.content_type or "").startswith("image/"))
    return {
        "name": _read(db, KEY_NAME),
        "phone": _read(db, KEY_PHONE),
        "address": _read(db, KEY_ADDRESS),
        "logo_attachment_id": logo_id,
        # 附件 ID 当查询参数：换 logo 即换 URL，浏览器与 nginx 的缓存自然失效
        "logo_url": f"{LOGO_PATH}?v={logo_id}" if has_logo else "",
    }


def get_logo_attachment_id(db: Session) -> int | None:
    """供匿名 logo 输出接口使用：只认设置里存的那个 ID，不接受外部入参。"""
    return _read_logo_attachment_id(db)


def save_company_info(
    db: Session,
    *,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    logo_attachment_id: int | None = None,
    clear_logo: bool = False,
) -> dict:
    if name is not None:
        upsert_setting(db, KEY_NAME, name.strip()[: MAX_LEN["name"]])
    if phone is not None:
        upsert_setting(db, KEY_PHONE, phone.strip()[: MAX_LEN["phone"]])
    if address is not None:
        upsert_setting(db, KEY_ADDRESS, address.strip()[: MAX_LEN["address"]])
    if clear_logo:
        upsert_setting(db, KEY_LOGO, "")
    elif logo_attachment_id is not None:
        att = get_attachment_by_id(db, attachment_id=logo_attachment_id)
        if not att:
            raise ValueError("logo 附件不存在")
        if not (att.content_type or "").startswith("image/"):
            raise ValueError("logo 必须是图片")
        upsert_setting(db, KEY_LOGO, str(logo_attachment_id))
    db.flush()
    return get_company_info(db)
