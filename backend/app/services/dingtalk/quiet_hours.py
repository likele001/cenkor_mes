"""静默时段"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from zoneinfo import ZoneInfo


def _parse_hm(s: str) -> time | None:
    try:
        h, m = s.strip().split(":")
        return time(int(h), int(m))
    except Exception:
        return None


def is_in_quiet_hours(cfg: dict, now: datetime | None = None) -> bool:
    qh = cfg.get("quiet_hours") or {}
    if not qh.get("enabled"):
        return False
    start = _parse_hm(str(qh.get("start") or "22:00"))
    end = _parse_hm(str(qh.get("end") or "07:00"))
    if not start or not end:
        return False
    now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    t = now.timetz().replace(tzinfo=None) if hasattr(now.timetz(), "replace") else now.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end


def next_send_time(cfg: dict, now: datetime | None = None) -> datetime | None:
    if not is_in_quiet_hours(cfg, now):
        return None
    qh = cfg.get("quiet_hours") or {}
    end = _parse_hm(str(qh.get("end") or "07:00"))
    if not end:
        return None
    now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    candidate = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate
