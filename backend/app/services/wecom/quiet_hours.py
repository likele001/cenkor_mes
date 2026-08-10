"""企业微信推送静默时段"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.wecom.settings import get_wecom_settings_raw


def _parse_hm(s: str) -> tuple[int, int]:
    parts = (s or "00:00").strip().split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def is_in_quiet_hours(cfg: dict, now: datetime | None = None) -> bool:
    qh = cfg.get("quiet_hours") or {}
    if not qh.get("enabled"):
        return False
    now = now or datetime.now()
    sh, sm = _parse_hm(str(qh.get("start") or "22:00"))
    eh, em = _parse_hm(str(qh.get("end") or "07:00"))
    cur = now.hour * 60 + now.minute
    start = sh * 60 + sm
    end = eh * 60 + em
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end


def next_send_time(cfg: dict, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    if not is_in_quiet_hours(cfg, now):
        return now
    qh = cfg.get("quiet_hours") or {}
    eh, em = _parse_hm(str(qh.get("end") or "07:00"))
    candidate = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate
