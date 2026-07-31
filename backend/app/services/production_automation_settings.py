"""生产自动化租户配置（tenant_settings）"""

from __future__ import annotations

import json
from copy import deepcopy

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY = "production.automation"

DEFAULTS: dict = {
    "enabled": False,
    "on_order_confirm": {
        "create_plan": False,
        "start_offset_days": 0,
        "run_pipeline_after_create": False,
    },
    "on_plan_saved": {
        "run_schedule": False,
        "engine": "ortools",
        "auto_release": False,
        "auto_dispatch": False,
        "allow_shortage": False,
    },
    "audit": {
        "prescreen_on_submit": True,
        "auto_leader_approve": False,
        "auto_qc_approve": False,
        "require_employee_photo": True,
        "vision_min_score": 0.75,
        "block_if_prior_reject": True,
    },
    "briefing": {
        "daily_enabled": False,
        "daily_hour": 8,
        "mode": "rule",
    },
    "alerts": {
        "notify_on_scan": True,
        "create_todo_on_critical": True,
    },
}


def _merge_dict(base: dict, patch: dict) -> dict:
    out = deepcopy(base)
    for k, v in patch.items():
        if k not in out:
            out[k] = v
            continue
        if isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dict(out[k], v)
        elif v is not None:
            out[k] = v
    return out


def get_automation_settings(db: Session, tenant_id: int) -> dict:
    row = get_setting(db, tenant_id, KEY)
    if not row or not row.value:
        return deepcopy(DEFAULTS)
    try:
        data = json.loads(row.value)
        if not isinstance(data, dict):
            return deepcopy(DEFAULTS)
        return _merge_dict(DEFAULTS, data)
    except Exception:
        return deepcopy(DEFAULTS)


def save_automation_settings(db: Session, tenant_id: int, payload: dict) -> dict:
    current = get_automation_settings(db, tenant_id)
    merged = _merge_dict(current, payload or {})
    upsert_setting(db, tenant_id=tenant_id, key=KEY, value=json.dumps(merged, ensure_ascii=False))
    return merged
