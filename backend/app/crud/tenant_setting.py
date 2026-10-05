# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_setting import TenantSetting


def get_setting(
    db: Session,
    tenant_id_or_key: str | int | None = None,
    key: str | None = None,
) -> TenantSetting | None:
    """兼容 SaaS 签名 get_setting(db, tenant_id, key) 和单用户签名 get_setting(db, key)."""
    actual_key = key if key is not None else tenant_id_or_key
    return db.scalar(select(TenantSetting).where(TenantSetting.key == actual_key))


def list_settings(db: Session, tenant_id: int | None = None, offset: int = 0, limit: int = 200) -> list[TenantSetting]:
    stmt = select(TenantSetting).order_by(TenantSetting.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def upsert_setting(
    db: Session,
    tenant_id_or_key: str | None = None,
    key_or_value: str | None = None,
    value: str | None = None,
    *,
    key: str | None = None,
) -> TenantSetting:
    """兼容三种签名：
    - upsert_setting(db, tenant_id, key, value)  SaaS 风格
    - upsert_setting(db, key, value)             单用户风格
    - upsert_setting(db, key=key, value=value)   关键字风格
    """
    if key is not None:
        actual_key, actual_value = key, value
    elif value is not None:
        actual_key, actual_value = key_or_value, value
    elif key_or_value is not None:
        actual_key, actual_value = tenant_id_or_key, key_or_value
    else:
        actual_key, actual_value = tenant_id_or_key, None
    item = get_setting(db, actual_key)
    if item:
        item.value = actual_value
        db.flush()
        return item
    item = TenantSetting(key=actual_key, value=actual_value)
    db.add(item)
    db.flush()
    return item


def delete_setting(db: Session, item: TenantSetting) -> None:
    db.delete(item)
    db.flush()
