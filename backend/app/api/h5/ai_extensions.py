# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""H5 智能中心：扩展可用性预检查。

一次性返回各 AI 扩展的「已安装 / 已启用 / 当前用户已授权」三态，员工端不必
逐个页面撞 403 才知道能不能用。只读、按登录用户计算，不暴露授权快照、版本、
健康状态等管理端字段。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.rbac import get_user_permission_codes
from app.extension_host.state import runtime
from app.models.user import User

router = APIRouter(prefix="/ai/extensions", tags=["h5-ai-extensions"])

# 与 AiHubPage.vue 的卡片、i18n 的扩展名保持一致；帮助页有核心降级能力，不做门控。
AI_EXTENSIONS: tuple[tuple[str, str], ...] = (
    ("ai_assistant", "ext.ai_assistant.view"),
    ("ai_anomaly", "ext.ai_anomaly.view"),
    ("ai_employee", "ext.ai_employee.view"),
    ("ai_insight", "ext.ai_insight.view"),
    ("ai_scene_reports", "ext.ai_scene_reports.view"),
)


@router.get("")
def list_ai_extensions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    granted = set(get_user_permission_codes(db, user.id))
    items = [
        {
            "key": key,
            "installed": key in runtime.installed,
            "enabled": runtime.is_enabled(key),
            "granted": perm in granted,
            "permission": perm,
        }
        for key, perm in AI_EXTENSIONS
    ]
    return ok({"items": items, "installed_total": len(runtime.installed)})
