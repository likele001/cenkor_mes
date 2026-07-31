"""考勤地理围栏校验（租户级可选配置，存 tenant_settings）"""

from __future__ import annotations

import json
import math

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting

KEY = "attendance.geofence"


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def get_geofence_config(db: Session) -> dict | None:
    row = get_setting(db, KEY)
    if not row or not row.value:
        return None
    try:
        cfg = json.loads(row.value) if isinstance(row.value, str) else row.value
    except Exception:
        return None
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return None
    lat, lng, radius = cfg.get("lat"), cfg.get("lng"), cfg.get("radius_m")
    if lat is None or lng is None or radius is None:
        return None
    return {"lat": float(lat), "lng": float(lng), "radius_m": float(radius)}


def assert_within_geofence(db: Session, lat: float | None, lng: float | None) -> None:
    cfg = get_geofence_config(db)
    if not cfg:
        return
    if lat is None or lng is None:
        raise ValueError("请开启定位权限后再打卡")
    dist = _haversine_m(lat, lng, cfg["lat"], cfg["lng"])
    if dist > cfg["radius_m"]:
        raise ValueError(f"不在打卡范围内（距打卡点约 {int(dist)} 米，允许 {int(cfg['radius_m'])} 米）")
