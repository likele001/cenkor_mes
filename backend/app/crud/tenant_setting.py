from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_setting import TenantSetting


def get_setting(db: Session, tenant_id_or_key, key: str | None = None) -> TenantSetting | None:
    """兼容 SaaS 签名 get_setting(db, tenant_id, key) 和单用户签名 get_setting(db, key)."""
    if key is None:
        # Called as get_setting(db, key) - single-user style
        actual_key = tenant_id_or_key
    else:
        # Called as get_setting(db, tenant_id, key) - SaaS style, ignore tenant_id
        actual_key = key
    return db.scalar(select(TenantSetting).where(TenantSetting.key == actual_key))


def list_settings(db: Session, tenant_id: int | None = None, offset: int = 0, limit: int = 200) -> list[TenantSetting]:
    stmt = select(TenantSetting).order_by(TenantSetting.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def upsert_setting(db: Session, tenant_id_or_key, key_or_value=None, value: str | None = None) -> TenantSetting:
    """兼容两种签名."""
    if value is not None:
        # Called as upsert_setting(db, tenant_id, key, value) - SaaS style
        actual_key = key_or_value
        actual_value = value
    elif key_or_value is not None:
        # Called as upsert_setting(db, key, value) - single-user style
        actual_key = tenant_id_or_key
        actual_value = key_or_value
    else:
        actual_key = tenant_id_or_key
        actual_value = None
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
