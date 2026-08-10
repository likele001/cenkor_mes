"""钉钉消息推送租户配置（tenant_settings）"""

from __future__ import annotations

import json
import os
from copy import deepcopy

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.crud.tenant_setting import get_setting, upsert_setting
from app.services.dingtalk.urls import get_oauth_redirect_uri

KEY = "dingtalk.notify"
SECRET_MASK = "********"

DEFAULT_GROUPS = [
    {"code": "production", "name": "生产群", "webhook_url": "", "webhook_secret": "", "enabled": True},
    {"code": "management", "name": "管理群", "webhook_url": "", "webhook_secret": "", "enabled": True},
    {"code": "factory", "name": "全厂群", "webhook_url": "", "webhook_secret": "", "enabled": True},
]

DEFAULT_RULES: dict = {
    "dispatch.assigned": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "report.submitted": {"enabled": True, "targets": ["dept_leaders", "workshop_leaders"], "channels": ["dingtalk", "in_app"]},
    "report.leader_approved": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "report.qc_approved": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "report.rejected": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "salary.slip_remind": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "salary.slip_reset": {"enabled": True, "targets": ["assigned_employee"], "channels": ["dingtalk", "in_app"]},
    "salary.slip_rejected": {"enabled": True, "targets": ["boss", "group:management"], "channels": ["dingtalk", "in_app"]},
    "order.customer_submitted": {"enabled": True, "targets": ["permission:order.manage", "group:management"], "channels": ["dingtalk", "in_app"]},
    "alert": {
        "enabled": True,
        "escalation": {
            "info": ["dept_managers"],
            "warning": ["dept_managers", "group:dept_auto"],
            "danger": ["dept_managers", "boss", "group:management"],
            "critical": ["dept_managers", "boss", "group:management", "group:factory"],
        },
        "channels": ["dingtalk", "in_app"],
    },
    "brief.daily": {"enabled": True, "targets": ["boss", "group:management", "group:factory"], "channels": ["dingtalk", "in_app"]},
    "plan.automation_failed": {"enabled": True, "targets": ["permission:plan.manage", "group:management"], "channels": ["dingtalk", "in_app"]},
}

DEFAULTS: dict = {
    "enabled": False,
    "corp_id": "",
    "app_key": "",
    "app_secret": "",
    "agent_id": "",
    "message_format": "action_card",
    "card_actions_enabled": True,
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


def _env_fallback() -> tuple[str, str, str, str]:
    return (
        (os.getenv("DINGTALK_CORP_ID") or "").strip(),
        (os.getenv("DINGTALK_APP_KEY") or "").strip(),
        (os.getenv("DINGTALK_APP_SECRET") or "").strip(),
        (os.getenv("DINGTALK_AGENT_ID") or "").strip(),
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


def get_dingtalk_credentials(db: Session, tenant_id: int | None = None) -> tuple[str, str, str, str]:
    # 单租户版：忽略 tenant_id（保留可选参数以兼容遗留调用方）
    cfg = get_dingtalk_settings_raw(db)
    corp_id = (cfg.get("corp_id") or "").strip()
    app_key = (cfg.get("app_key") or "").strip()
    app_secret = (cfg.get("app_secret") or "").strip()
    agent_id = (cfg.get("agent_id") or "").strip()
    if not app_key or not app_secret:
        env_corp, env_key, env_secret, env_agent = _env_fallback()
        corp_id = corp_id or env_corp
        app_key = app_key or env_key
        app_secret = app_secret or env_secret
        agent_id = agent_id or env_agent
    return corp_id, app_key, app_secret, agent_id


def get_dingtalk_settings_raw(db: Session, tenant_id: int | None = None) -> dict:
    # 单租户版：忽略 tenant_id（保留可选参数以兼容遗留调用方）
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


def get_dingtalk_settings_admin(db: Session) -> dict:
    cfg = get_dingtalk_settings_raw(db)
    secret = (cfg.get("app_secret") or "").strip()
    app_key = (cfg.get("app_key") or "").strip()
    corp_id = (cfg.get("corp_id") or "").strip()
    agent_id = (cfg.get("agent_id") or "").strip()
    oauth_redirect_url = get_oauth_redirect_uri(cfg)
    return {
        "enabled": bool(cfg.get("enabled")),
        "corp_id": corp_id,
        "app_key": app_key,
        "agent_id": agent_id,
        "corp_id_configured": bool(corp_id),
        "app_key_configured": bool(app_key),
        "agent_id_configured": bool(agent_id),
        "app_secret_configured": bool(secret),
        "app_secret_masked": SECRET_MASK if secret else "",
        "message_format": cfg.get("message_format") or "action_card",
        "card_actions_enabled": bool(cfg.get("card_actions_enabled", True)),
        "h5_public_base_url": cfg.get("h5_public_base_url") or "",
        "admin_public_base_url": cfg.get("admin_public_base_url") or "",
        "api_public_base_url": cfg.get("api_public_base_url") or "",
        "h5_public_base_url_default": app_settings.H5_PUBLIC_BASE_URL or "",
        "api_public_base_url_default": app_settings.PUBLIC_BASE_URL or "",
        "oauth_redirect_url": oauth_redirect_url,
        "groups": cfg.get("groups") or deepcopy(DEFAULT_GROUPS),
        "rules": cfg.get("rules") or deepcopy(DEFAULT_RULES),
        "quiet_hours": cfg.get("quiet_hours") or deepcopy(DEFAULTS["quiet_hours"]),
        "event_catalog": EVENT_CATALOG,
        "target_options": TARGET_OPTIONS,
    }


def save_dingtalk_settings(db: Session, payload: dict) -> dict:
    current = get_dingtalk_settings_raw(db)
    patch = dict(payload or {})

    if "app_secret" in patch:
        secret_str = str(patch.pop("app_secret") or "").strip()
        if secret_str and secret_str != SECRET_MASK:
            current["app_secret"] = secret_str
        elif secret_str == "":
            current["app_secret"] = ""

    for field in ("corp_id", "app_key", "agent_id"):
        if field in patch:
            val = str(patch.pop(field) or "").strip()
            if val:
                current[field] = val

    merged = _merge_dict(current, patch)
    upsert_setting(db, KEY, json.dumps(merged, ensure_ascii=False))
    return get_dingtalk_settings_admin(db)


def get_group_webhook(cfg: dict, code: str) -> tuple[str, str]:
    for g in cfg.get("groups") or []:
        if g.get("code") == code and g.get("enabled", True):
            return (g.get("webhook_url") or "").strip(), (g.get("webhook_secret") or "").strip()
    return "", ""


def is_dingtalk_enabled(db: Session, tenant_id: int | None = None) -> bool:
    # 单租户版：忽略 tenant_id（保留可选参数以兼容遗留调用方）
    cfg = get_dingtalk_settings_raw(db)
    if not cfg.get("enabled"):
        return False
    _, app_key, app_secret, _ = get_dingtalk_credentials(db)
    return bool(app_key and app_secret)
