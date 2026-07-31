"""租户工厂助手 system prompt 自定义"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY = "ai.boss_system_prompt"
MAX_LEN = 2000


def get_boss_prompt(db: Session, tenant_id: int) -> str:
    row = get_setting(db, tenant_id, KEY)
    if not row or not row.value:
        return ""
    return str(row.value).strip()[:MAX_LEN]


def get_prompt_settings_admin(db: Session, tenant_id: int) -> dict:
    return {"prompt": get_boss_prompt(db, tenant_id), "max_length": MAX_LEN}


def save_prompt_settings(db: Session, tenant_id: int, prompt: str | None) -> dict:
    text = (prompt or "").strip()[:MAX_LEN]
    upsert_setting(db, tenant_id, KEY, text or None)
    return get_prompt_settings_admin(db, tenant_id)
