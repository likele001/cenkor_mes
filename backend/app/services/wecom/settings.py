"""企业微信消息推送租户配置（tenant_settings）"""

from __future__ import annotations

import json
import os
from copy import deepcopy

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.crud.tenant_setting import get_setting, upsert_setting
from app.services.wecom.urls import get_events_callback_url, get_oauth_redirect_uri

KEY = "wecom.notify"
SECRET_MASK = "********"

DEFAULT_GROUPS = [
    {"code": "production", "name": "生产群", "webhook_url": "", "enabled": True},
    {"code": "management", "name": "管理群", "webhook_url": "", "enabled": True},
    {"code": "factory", "name": "全厂群", "webhook_url": "", "enabled": True},
]

DEFAULT_RULES: dict = {
    "dispatch.assigned": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "report.submitted": {
        "enabled": True,
        "targets": ["dept_leaders", "workshop_leaders"],
        "channels": ["wecom", "in_app"],
    },
    "report.leader_approved": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "report.qc_approved": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "report.rejected": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "salary.slip_remind": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "salary.slip_reset": {
        "enabled": True,
        "targets": ["assigned_employee"],
        "channels": ["wecom", "in_app"],
    },
    "salary.slip_rejected": {
        "enabled": True,
        "targets": ["boss", "group:management"],
        "channels": ["wecom", "in_app"],
    },
    "order.customer_submitted": {
        "enabled": True,
        "targets": ["permission:order.manage", "group:management"],
        "channels": ["wecom", "in_app"],
    },
    "alert": {
        "enabled": True,
        "escalation": {
            "info": ["dept_managers"],
            "warning": ["dept_managers", "group:dept_auto"],
            "danger": ["dept_managers", "boss", "group:management"],
            "critical": ["dept_managers", "boss", "group:management", "group:factory"],
        },
        "channels": ["wecom", "in_app"],
    },
    "brief.daily": {
        "enabled": True,
        "targets": ["boss", "group:management", "group:factory"],
        "channels": ["wecom", "in_app"],
    },
    "plan.automation_failed": {
        "enabled": True,
        "targets": ["permission:plan.manage", "group:management"],
        "channels": ["wecom", "in_app"],
    },
}

DEFAULTS: dict = {
    "enabled": False,
    "corp_id": "",
    "agent_id": "",
    "corp_secret": "",
    "token": "",
    "encoding_aes_key": "",
    "message_format": "markdown",
    "h5_public_base_url": "",
    "admin_public_base_url": "",
    "api_public_base_url": "",
    "groups": deepcopy(DEFAULT_GROUPS),
    "rules": deepcopy(DEFAULT_RULES),
    "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00"},
}

EVENT_CATALOG = [
    {"code": "dispatch.assigned", "name": "派工通知", "category": "production"},
    {"code": "report.submitted", "name": "报工待审", "category": "production"},
    {"code": "report.leader_approved", "name": "报工初审通过", "category": "production"},
    {"code": "report.qc_approved", "name": "报工终审通过", "category": "production"},
    {"code": "report.rejected", "name": "报工驳回", "category": "production"},
    {"code": "salary.slip_remind", "name": "工资条催签", "category": "salary"},
    {"code": "salary.slip_reset", "name": "工资条重置", "category": "salary"},
    {"code": "salary.slip_rejected", "name": "工资条拒签", "category": "salary"},
    {"code": "order.customer_submitted", "name": "客户下单待确认", "category": "order"},
    {"code": "alert", "name": "AI/业务预警", "category": "alert"},
    {"code": "brief.daily", "name": "每日生产简报", "category": "alert"},
    {"code": "plan.automation_failed", "name": "生产自动化失败", "category": "plan"},
]

TARGET_OPTIONS = [
    {"code": "assigned_employee", "name": "事件关联员工"},
    {"code": "dept_leaders", "name": "部门班组长"},
    {"code": "dept_managers", "name": "部门管理（含上级部门）"},
    {"code": "workshop_leaders", "name": "车间负责人"},
    {"code": "boss", "name": "老板/厂长"},
    {"code": "group:production", "name": "生产群"},
    {"code": "group:management", "name": "管理群"},
    {"code": "group:factory", "name": "全厂群"},
    {"code": "group:dept_auto", "name": "部门关联群（自动）"},
    {"code": "permission:order.manage", "name": "订单管理权限"},
    {"code": "permission:plan.manage", "name": "计划管理权限"},
    {"code": "permission:report.audit", "name": "报工审核权限"},
    {"code": "permission:ai.alert.view", "name": "AI预警查看权限"},
]


def _env_fallback() -> tuple[str, str, str]:
    return (
        (os.getenv("WECOM_CORP_ID") or "").strip(),
        (os.getenv("WECOM_CORP_SECRET") or "").strip(),
        (os.getenv("WECOM_AGENT_ID") or "").strip(),
    )


def _merge_dict(base: dict, patch: dict) -> dict:
    out = deepcopy(base)
    for k, v in patch.items():
        if k not in out:
            out[k] = v
            continue
        if isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dict(out[k], v)
        elif isinstance(out[k], list) and isinstance(v, list):
            out[k] = v
        elif v is not None:
            out[k] = v
    return out


def get_wecom_credentials(db: Session, tenant_id: int | None = None) -> tuple[str, str, str]:
    cfg = get_wecom_settings_raw(db)
    corp_id = (cfg.get("corp_id") or "").strip()
    corp_secret = (cfg.get("corp_secret") or "").strip()
    agent_id = (cfg.get("agent_id") or "").strip()
    if not corp_id or not corp_secret:
        env_id, env_secret, env_agent = _env_fallback()
        corp_id = corp_id or env_id
        corp_secret = corp_secret or env_secret
        agent_id = agent_id or env_agent
    return corp_id, corp_secret, agent_id


def get_wecom_settings_raw(db: Session, tenant_id: int | None = None) -> dict:
    row = get_setting(db, KEY)
    if not row or not row.value:
        return deepcopy(DEFAULTS)
    try:
        data = json.loads(row.value)
        if not isinstance(data, dict):
            return deepcopy(DEFAULTS)
        return _merge_dict(DEFAULTS, data)
    except Exception:
        return deepcopy(DEFAULTS)


def get_wecom_settings_admin(db: Session, tenant_id: int | None = None) -> dict:
    cfg = get_wecom_settings_raw(db)
    secret = (cfg.get("corp_secret") or "").strip()
    corp_id = (cfg.get("corp_id") or "").strip()
    agent_id = (cfg.get("agent_id") or "").strip()
    callback_url = get_events_callback_url(cfg)
    oauth_redirect_url = get_oauth_redirect_uri(cfg)
    return {
        "enabled": bool(cfg.get("enabled")),
        "corp_id": corp_id,
        "agent_id": agent_id,
        "corp_id_configured": bool(corp_id),
        "agent_id_configured": bool(agent_id),
        "corp_secret_configured": bool(secret),
        "corp_secret_masked": SECRET_MASK if secret else "",
        "token": (cfg.get("token") or ""),
        "token_configured": bool((cfg.get("token") or "").strip()),
        "encoding_aes_key": (cfg.get("encoding_aes_key") or ""),
        "encoding_aes_key_configured": bool((cfg.get("encoding_aes_key") or "").strip()),
        "message_format": cfg.get("message_format") or "markdown",
        "h5_public_base_url": cfg.get("h5_public_base_url") or "",
        "admin_public_base_url": cfg.get("admin_public_base_url") or "",
        "api_public_base_url": cfg.get("api_public_base_url") or "",
        "h5_public_base_url_default": app_settings.H5_PUBLIC_BASE_URL or "",
        "api_public_base_url_default": app_settings.PUBLIC_BASE_URL or "",
        "callback_url": callback_url,
        "oauth_redirect_url": oauth_redirect_url,
        "groups": cfg.get("groups") or deepcopy(DEFAULT_GROUPS),
        "rules": cfg.get("rules") or deepcopy(DEFAULT_RULES),
        "quiet_hours": cfg.get("quiet_hours") or deepcopy(DEFAULTS["quiet_hours"]),
        "event_catalog": EVENT_CATALOG,
        "target_options": TARGET_OPTIONS,
    }


def save_wecom_settings(db: Session, payload: dict, tenant_id: int | None = None) -> dict:
    current = get_wecom_settings_raw(db)
    patch = dict(payload or {})

    if "corp_secret" in patch:
        secret_str = str(patch.pop("corp_secret") or "").strip()
        if secret_str and secret_str != SECRET_MASK:
            current["corp_secret"] = secret_str
        elif secret_str == "":
            current["corp_secret"] = ""

    if "encoding_aes_key" in patch:
        val = str(patch.pop("encoding_aes_key") or "").strip()
        if val and val != SECRET_MASK:
            current["encoding_aes_key"] = val
        elif val == "":
            current["encoding_aes_key"] = ""

    if "token" in patch:
        val = str(patch.pop("token") or "").strip()
        if val and val != SECRET_MASK:
            current["token"] = val
        elif val == "":
            current["token"] = ""

    # 留空表示不修改，避免刷新/误保存把已配置凭证清空
    if "corp_id" in patch:
        val = str(patch.pop("corp_id") or "").strip()
        if val:
            current["corp_id"] = val

    if "agent_id" in patch:
        val = str(patch.pop("agent_id") or "").strip()
        if val:
            current["agent_id"] = val

    merged = _merge_dict(current, patch)
    upsert_setting(db, KEY, json.dumps(merged, ensure_ascii=False))
    return get_wecom_settings_admin(db)


def get_group_webhook(cfg: dict, code: str) -> str:
    for g in cfg.get("groups") or []:
        if g.get("code") == code and g.get("enabled", True):
            return (g.get("webhook_url") or "").strip()
    return ""


def is_wecom_enabled(db: Session, tenant_id: int | None = None) -> bool:
    cfg = get_wecom_settings_raw(db)
    if not cfg.get("enabled"):
        return False
    corp_id, corp_secret, _ = get_wecom_credentials(db)
    return bool(corp_id and corp_secret)
