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

# ── 工序流转策略（报工柔性化）──
KEY_SEQUENCE_POLICY = "production.report.sequence_policy"
SEQUENCE_POLICIES = ("strict", "soft", "free")
SEQUENCE_POLICY_LABELS = {
    "strict": "强制顺序（旧方案）",
    "soft": "柔性顺序（默认）",
    "free": "自由报工",
}
SEQUENCE_POLICY_HELP = {
    "strict": "必须上一道工序终审良品后才能报下一道，首工序为开关。",
    "soft": "允许后道工序先报，上一道未完成时给软提示确认，不硬拦。",
    "free": "完全不卡顺序，谁先报都行，仅做异常预警。",
}
DEFAULT_SEQUENCE_POLICY = "soft"


def normalize_sequence_policy(raw: str | None) -> str:
    p = (raw or "").strip().lower()
    if p in SEQUENCE_POLICIES:
        return p
    return DEFAULT_SEQUENCE_POLICY


def get_sequence_policy(db: Session, tenant_id: int = 0) -> str:
    row = get_setting(db, KEY_SEQUENCE_POLICY)
    return normalize_sequence_policy(row.value if row else None)


def save_sequence_policy(db: Session, tenant_id: int = 0, policy: str = "soft") -> dict:
    p = normalize_sequence_policy(policy)
    upsert_setting(db, KEY_SEQUENCE_POLICY, p)
    db.flush()
    return {
        "sequence_policy": p,
        "label": SEQUENCE_POLICY_LABELS.get(p, p),
        "help": SEQUENCE_POLICY_HELP.get(p, ""),
    }


def get_sequence_policy_options() -> list[dict]:
    return [
        {"value": k, "label": SEQUENCE_POLICY_LABELS[k], "help": SEQUENCE_POLICY_HELP[k]}
        for k in SEQUENCE_POLICIES
    ]


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
        "sequence_policy": get_sequence_policy(db),
        "sequence_policy_label": SEQUENCE_POLICY_LABELS.get(get_sequence_policy(db)),
        "sequence_policies": get_sequence_policy_options(),
    }


def save_report_mode_settings(db: Session, tenant_id: int = 0, default_mode: str = "batch", sequence_policy: str | None = None) -> dict:
    mode = normalize_mode(default_mode)
    upsert_setting(db, KEY_DEFAULT_MODE, mode)
    if sequence_policy is not None:
        save_sequence_policy(db, tenant_id, sequence_policy)
    db.flush()
    return get_report_mode_settings(db, tenant_id)


def get_default_report_mode(db: Session) -> str:
    return get_report_mode_settings(db, 0)["default_mode"]


def use_unit_report_mode(db: Session) -> bool:
    return get_default_report_mode(db) == "unit"


def use_batch_report_mode(db: Session) -> bool:
    return get_default_report_mode(db) == "batch"
