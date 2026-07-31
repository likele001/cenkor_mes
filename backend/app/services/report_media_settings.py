"""报工/审核影像：租户级拍摄时长、大小、数量（仅现场拍摄，控制服务器压力）"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting

KEY_MAX_VIDEO_SECONDS = "report.media.max_video_seconds"
KEY_MAX_VIDEO_MB = "report.media.max_video_mb"
KEY_MAX_VIDEO_COUNT = "report.media.max_video_count"
KEY_MAX_PHOTO_COUNT = "report.media.max_photo_count"
KEY_CAMERA_ONLY = "report.media.camera_only"

DEFAULTS = {
    KEY_MAX_VIDEO_SECONDS: 15,
    KEY_MAX_VIDEO_MB: 8,
    KEY_MAX_VIDEO_COUNT: 3,
    KEY_MAX_PHOTO_COUNT: 5,
    KEY_CAMERA_ONLY: True,
}


def _parse_int(raw: str | None, default: int, min_v: int, max_v: int) -> int:
    try:
        v = int(str(raw or "").strip())
    except (TypeError, ValueError):
        return default
    return max(min_v, min(max_v, v))


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def get_report_media_settings(db: Session, tenant_id: int = 0) -> dict:
    def _get(key: str) -> str | None:
        row = get_setting(db, key)
        return row.value if row and row.value is not None else None

    max_seconds = _parse_int(_get(KEY_MAX_VIDEO_SECONDS), DEFAULTS[KEY_MAX_VIDEO_SECONDS], 5, 120)
    max_video_mb = _parse_int(_get(KEY_MAX_VIDEO_MB), DEFAULTS[KEY_MAX_VIDEO_MB], 1, 50)
    max_video_count = _parse_int(_get(KEY_MAX_VIDEO_COUNT), DEFAULTS[KEY_MAX_VIDEO_COUNT], 1, 10)
    max_photo_count = _parse_int(_get(KEY_MAX_PHOTO_COUNT), DEFAULTS[KEY_MAX_PHOTO_COUNT], 1, 20)
    camera_only = _parse_bool(_get(KEY_CAMERA_ONLY), DEFAULTS[KEY_CAMERA_ONLY])
    return {
        "max_video_seconds": max_seconds,
        "max_video_mb": max_video_mb,
        "max_video_count": max_video_count,
        "max_photo_count": max_photo_count,
        "camera_only": camera_only,
        "max_video_bytes": max_video_mb * 1024 * 1024,
    }


def save_report_media_settings(db: Session, tenant_id: int = 0, payload: dict | None = None) -> dict:
    from app.crud.tenant_setting import upsert_setting

    if payload is None:
        payload = {}
    ms = max(5, min(120, int(payload.get("max_video_seconds", DEFAULTS[KEY_MAX_VIDEO_SECONDS]))))
    mb = max(1, min(50, int(payload.get("max_video_mb", DEFAULTS[KEY_MAX_VIDEO_MB]))))
    vc = max(1, min(10, int(payload.get("max_video_count", DEFAULTS[KEY_MAX_VIDEO_COUNT]))))
    pc = max(1, min(20, int(payload.get("max_photo_count", DEFAULTS[KEY_MAX_PHOTO_COUNT]))))
    cam = payload.get("camera_only", DEFAULTS[KEY_CAMERA_ONLY])
    upsert_setting(db, KEY_MAX_VIDEO_SECONDS, str(ms))
    upsert_setting(db, KEY_MAX_VIDEO_MB, str(mb))
    upsert_setting(db, KEY_MAX_VIDEO_COUNT, str(vc))
    upsert_setting(db, KEY_MAX_PHOTO_COUNT, str(pc))
    upsert_setting(db, KEY_CAMERA_ONLY, "true" if cam else "false")
    db.flush()
    return get_report_media_settings(db, tenant_id)
