from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

KEY_DEFAULT_MODE = "production.report.default_mode"

MODES = ("batch", "unit", "lot")

MODE_LABELS = {
    "batch": "批量报工",
    "unit": "逐件报工（件次+成品码）",
    "lot": "批次流转（预留）",
}

MODE_HELP = {
    "batch": "扫任务码填写合格/不良数量，按班长派工计件；适合大多数车间大批量。",
    "unit": "逐件拍照/视频、件次槽位、首工序成品码；适合精品线或强追溯。",
    "lot": "按扎/筐批次码流转（功能预留，后期按企业定制）。",
}

DEFAULT_MODE = "batch"


def normalize_mode(raw: str | None) -> str:
    m = (raw or "").strip().lower()
    if m in MODES:
        return m
    return DEFAULT_MODE


def get_report_mode_settings(db: Session, tenant_id: int = 0) -> dict:
    row = get_setting(db, KEY_DEFAULT_MODE)
    mode = normalize_mode(row.value if row else None)
    return {
        "default_mode": mode,
        "default_mode_label": MODE_LABELS.get(mode, mode),
        "modes": [
            {"value": k, "label": MODE_LABELS[k], "help": MODE_HELP[k], "enabled": k != "lot"}
            for k in MODES
        ],
    }


def save_report_mode_settings(db: Session, tenant_id: int = 0, default_mode: str = "batch") -> dict:
    mode = normalize_mode(default_mode)
    upsert_setting(db, KEY_DEFAULT_MODE, mode)
    db.flush()
    return get_report_mode_settings(db, tenant_id)


def get_default_report_mode(db: Session) -> str:
    return get_report_mode_settings(db, 0)["default_mode"]


def use_unit_report_mode(db: Session) -> bool:
    return get_default_report_mode(db) == "unit"


def use_batch_report_mode(db: Session) -> bool:
    return get_default_report_mode(db) == "batch"
