# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主固定 API（登录态）：扩展列表 / 事件钩子可视化 / 前端插件获取。

仅服务于 admin 前端的「扩展加载器」动态注入与「事件钩子」管理页。MES 不提供任何应用
安装 / 授权管理界面——应用目录、发卡、实例绑定与吊销均在独立应用中心完成。
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.deps import require_permissions
from app.core.response import ok
from app.extension_host.events import event_bus, event_recorder
from app.extension_host.state import runtime

router = APIRouter(tags=["admin-extensions"])

_SETTING_MGMT = [Depends(require_permissions(["setting.manage"]))]


@router.get("")
def list_extensions():
    """已安装扩展及启用状态（前端加载器据此决定加载哪些插件）。"""
    return ok({"items": runtime.status_list(), "synced_at": runtime.synced_at})


# ---------- 事件钩子可视化（必须放在 /{key}/plugin.js 之前，避免 events 被当作 key 匹配）----------

@router.get("/events/catalog", dependencies=_SETTING_MGMT)
def get_event_catalog():
    """事件契约表（静态）：28 个事件名 + phase + payload 字段说明。"""
    return ok({"items": event_bus.catalog()})


@router.get("/events/subscriptions", dependencies=_SETTING_MGMT)
def get_event_subscriptions():
    """订阅关系：每个扩展订阅了哪些事件，含启用状态。"""
    installed_keys = {k: v["manifest"].name for k, v in runtime.installed.items()}
    subs = event_bus.snapshot_subscriptions()
    for s in subs:
        s["extension_name"] = installed_keys.get(s["key"], "（未知扩展）")
        s["enabled"] = runtime.is_enabled(s["key"])
    return ok({"items": subs})


@router.get("/events/recent", dependencies=_SETTING_MGMT)
def get_recent_events(
    limit: int = Query(default=100, ge=1, le=200),
    event_name: str | None = Query(default=None),
    ext_key: str | None = Query(default=None),
    phase: str | None = Query(default=None, pattern="^(notify|intercept)$"),
):
    """最近事件流（环形缓冲，重启清零）。"""
    records = event_recorder.snapshot(
        limit=limit, event_name=event_name, ext_key=ext_key, phase=phase,
    )
    return ok({"items": [asdict(r) for r in records]})


@router.get("/events/stats", dependencies=_SETTING_MGMT)
def get_event_stats():
    """按 (事件, 扩展) 聚合的统计：total / errors / slow / rejections / last_at。"""
    return ok({"items": list(event_recorder.stats().values())})


# ---------- 扩展前端插件脚本 ----------

@router.get("/{key}/plugin.js")
def get_plugin_js(key: str):
    """返回扩展前端插件脚本（仅启用状态可获取）。"""
    info = runtime.installed.get(key)
    if not info:
        raise HTTPException(status_code=404, detail="扩展不存在")
    if not runtime.is_enabled(key):
        raise HTTPException(status_code=403, detail="扩展未启用")
    file = info["path"] / "frontend" / "plugin.js"
    if not file.is_file():
        raise HTTPException(status_code=404, detail="该扩展没有前端插件")
    return FileResponse(str(file), media_type="application/javascript")
