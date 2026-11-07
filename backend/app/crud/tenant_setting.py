# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_setting import TenantSetting


def get_setting(
    db: Session,
    tenant_id_or_key: str | int | None = None,
    key: str | None = None,
    *,
    tenant_id: int | None = None,
) -> TenantSetting | None:
    """兼容三种调用：
    - get_setting(db, tenant_id, key)            SaaS 位置参数风格
    - get_setting(db, key)                       单用户风格
    - get_setting(db, tenant_id=..., key=...)    SaaS 关键字风格

    独立版 TenantSetting 没有 tenant_id 列，全实例只有一套配置，故 tenant_id 只吸收不用。
    放在 keyword-only 里，不影响原有位置参数语义。在兼容层收口是为了让从 SaaS 版
    搬过来的调用点（如 admin/production/crm.py）不必逐个改写，避免逐端点补丁漏改。
    """
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
    tenant_id: int | None = None,
) -> TenantSetting:
    """兼容四种签名：
    - upsert_setting(db, tenant_id, key, value)              SaaS 位置参数风格
    - upsert_setting(db, key, value)                         单用户风格
    - upsert_setting(db, key=key, value=value)               关键字风格
    - upsert_setting(db, tenant_id=..., key=..., value=...)   SaaS 关键字风格

    tenant_id 在独立版中只吸收不用（单租户）。与 get_setting 同理，在兼容层收口。
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
