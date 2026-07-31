"""AI 预警阈值（tenant_settings）"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY = "ai.alert.thresholds"

DEFAULTS = {
    "pending_audit": 50,
    "yield_drop_delta": 0.05,
    "pending_tasks": 30,
    "unassigned_sample_min": 3,
}


def get_alert_thresholds(db: Session, tenant_id: int) -> dict:
    row = get_setting(db, tenant_id, KEY)
    if not row or not row.value:
        return dict(DEFAULTS)
    try:
        data = json.loads(row.value)
        if not isinstance(data, dict):
            return dict(DEFAULTS)
        out = dict(DEFAULTS)
        for k in DEFAULTS:
            if k in data:
                try:
                    out[k] = type(DEFAULTS[k])(data[k])
                except (TypeError, ValueError):
                    pass
        return out
    except Exception:
        return dict(DEFAULTS)


def save_alert_thresholds(db: Session, tenant_id: int, payload: dict) -> dict:
    current = get_alert_thresholds(db, tenant_id)
    for k in DEFAULTS:
        if k in payload and payload[k] is not None:
            current[k] = type(DEFAULTS[k])(payload[k])
    upsert_setting(db, tenant_id=tenant_id, key=KEY, value=json.dumps(current, ensure_ascii=False))
    return current
