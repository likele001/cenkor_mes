"""租户级 AI 网关覆盖（SaaS 可选独立 Key / Base URL）"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY = "ai.gateway_override"
SECRET_MASK = "********"

DEFAULTS = {
    "enabled": False,
    "base_url": "",
    "api_key": "",
    "model_id": "",
    "timeout_seconds": 120,
}


def _parse_raw(value: str | None) -> dict:
    if not value:
        return dict(DEFAULTS)
    try:
        data = json.loads(value)
        if not isinstance(data, dict):
            return dict(DEFAULTS)
    except Exception:
        return dict(DEFAULTS)
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in data and data[k] is not None:
            if k == "enabled":
                out[k] = bool(data[k])
            elif k == "timeout_seconds":
                try:
                    out[k] = int(data[k])
                except (TypeError, ValueError):
                    pass
            else:
                out[k] = str(data[k]).strip()
    return out


def get_tenant_gateway_override(db: Session, tenant_id: int) -> dict | None:
    """运行时解析：启用且 base_url + api_key 齐全时返回覆盖配置。"""
    row = get_setting(db, tenant_id, KEY)
    cfg = _parse_raw(row.value if row else None)
    if not cfg.get("enabled"):
        return None
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    api_key = (cfg.get("api_key") or "").strip()
    if not base_url or not api_key:
        return None
    timeout = int(cfg.get("timeout_seconds") or DEFAULTS["timeout_seconds"])
    timeout = max(10, min(600, timeout))
    model_id = (cfg.get("model_id") or "").strip()
    return {
        "base_url": base_url,
        "api_key": api_key,
        "model_id": model_id,
        "timeout_seconds": timeout,
    }


def get_gateway_settings_admin(db: Session, tenant_id: int) -> dict:
    row = get_setting(db, tenant_id, KEY)
    cfg = _parse_raw(row.value if row else None)
    api_key = (cfg.get("api_key") or "").strip()
    return {
        "enabled": bool(cfg.get("enabled")),
        "base_url": cfg.get("base_url") or "",
        "api_key_configured": bool(api_key),
        "api_key_masked": SECRET_MASK if api_key else "",
        "model_id": cfg.get("model_id") or "",
        "timeout_seconds": int(cfg.get("timeout_seconds") or DEFAULTS["timeout_seconds"]),
    }


def save_gateway_settings(db: Session, tenant_id: int, payload: dict) -> dict:
    row = get_setting(db, tenant_id, KEY)
    current = _parse_raw(row.value if row else None)

    if "enabled" in payload and payload["enabled"] is not None:
        current["enabled"] = bool(payload["enabled"])
    if "base_url" in payload and payload["base_url"] is not None:
        current["base_url"] = str(payload["base_url"]).strip()
    if "model_id" in payload and payload["model_id"] is not None:
        current["model_id"] = str(payload["model_id"]).strip()
    if "timeout_seconds" in payload and payload["timeout_seconds"] is not None:
        try:
            current["timeout_seconds"] = max(10, min(600, int(payload["timeout_seconds"])))
        except (TypeError, ValueError):
            pass

    api_key = payload.get("api_key")
    if api_key is not None:
        key_str = str(api_key).strip()
        if key_str and key_str != SECRET_MASK:
            current["api_key"] = key_str
        elif key_str == "":
            current["api_key"] = ""

    upsert_setting(db, tenant_id=tenant_id, key=KEY, value=json.dumps(current, ensure_ascii=False))
    return get_gateway_settings_admin(db, tenant_id)
