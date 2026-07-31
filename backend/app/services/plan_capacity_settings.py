from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY_UNIT = "plan.capacity.unit"
KEY_MINUTES = "plan.capacity.minutes_per_day"
KEY_LEGACY = "plan.capacity.per_day"
KEY_WORKSHOPS = "plan.capacity.workshops.minutes_per_day"
KEY_USERS = "plan.capacity.users.minutes_per_day"
KEY_EQUIPMENTS = "plan.capacity.equipments.minutes_per_day"

UNITS = ("pieces", "minutes")
DEFAULT_PIECES = 300
DEFAULT_MINUTES = 480


def normalize_capacity_unit(raw: str | None) -> str:
    u = (raw or "").strip().lower()
    return u if u in UNITS else "pieces"


def get_capacity_unit(db: Session, tenant_id: int = 0) -> str:
    row = get_setting(db, KEY_UNIT)
    return normalize_capacity_unit(row.value if row else None)


def save_capacity_unit(db: Session, tenant_id: int = 0, unit: str = "pieces") -> str:
    u = normalize_capacity_unit(unit)
    upsert_setting(db, KEY_UNIT, u)
    return u


def capacity_unit_label(unit: str) -> str:
    return "件/天" if unit == "pieces" else "分钟/天"


def get_default_capacity(db: Session, tenant_id: int = 0) -> int:
    unit = get_capacity_unit(db, tenant_id)
    fallback = DEFAULT_PIECES if unit == "pieces" else DEFAULT_MINUTES
    it = get_setting(db, KEY_MINUTES)
    val = fallback
    if it and it.value:
        try:
            val = int(it.value)
        except ValueError:
            val = fallback

    if val < 1 and unit == "minutes":
        legacy = get_setting(db, KEY_LEGACY)
        if legacy and legacy.value:
            try:
                legacy_val = int(legacy.value)
                if legacy_val >= 60:
                    val = legacy_val
            except ValueError:
                pass

    if val <= 0:
        val = fallback
    return min(int(val), 10000)


def get_capacity_meta(db: Session, tenant_id: int = 0) -> dict:
    unit = get_capacity_unit(db, tenant_id)
    return {
        "unit": unit,
        "unit_label": capacity_unit_label(unit),
        "capacity": get_default_capacity(db, tenant_id),
    }


def _parse_capacity_map(raw, *, id_key: str) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out: dict = {}
    if isinstance(v, dict):
        for k, vv in v.items():
            try:
                n = int(vv)
            except (TypeError, ValueError):
                continue
            if n > 0:
                out[k] = min(n, 10000)
        return out
    if isinstance(v, list):
        for row in v:
            if not isinstance(row, dict):
                continue
            kid = row.get(id_key)
            try:
                n = int(row.get("capacity_minutes"))
            except (TypeError, ValueError):
                continue
            if n > 0:
                if id_key == "workshop":
                    k = str(kid or "").strip()
                    if k:
                        out[k[:64]] = min(n, 10000)
                else:
                    try:
                        out[int(kid)] = min(n, 10000)
                    except (TypeError, ValueError):
                        pass
    return out


def get_workshop_capacity_map(db: Session, tenant_id: int = 0) -> dict[str, int]:
    it = get_setting(db, KEY_WORKSHOPS)
    return _parse_capacity_map(it.value if it else None, id_key="workshop")


def get_user_capacity_map(db: Session, tenant_id: int = 0) -> dict[int, int]:
    it = get_setting(db, KEY_USERS)
    raw = _parse_capacity_map(it.value if it else None, id_key="user_id")
    return {int(k): int(v) for k, v in raw.items()}


def get_equipment_capacity_map(db: Session, tenant_id: int = 0) -> dict[int, int]:
    it = get_setting(db, KEY_EQUIPMENTS)
    raw = _parse_capacity_map(it.value if it else None, id_key="equipment_id")
    return {int(k): int(v) for k, v in raw.items()}


def task_load_qty(*, planned_qty: int, std_minutes: int, unit: str) -> int:
    qty = int(planned_qty or 0)
    if unit == "pieces":
        return max(qty, 0)
    mins = qty * int(std_minutes or 0)
    return mins if mins > 0 else qty
