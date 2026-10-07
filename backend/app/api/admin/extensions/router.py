# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主固定 API（登录态）：扩展列表 / 前端插件获取。

仅服务于 admin 前端的「扩展加载器」动态注入。MES 不提供任何应用
安装 / 授权管理界面——应用目录、发卡、实例绑定与吊销均在独立应用中心完成。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.response import ok
from app.extension_host.state import runtime

router = APIRouter(tags=["admin-extensions"])


@router.get("")
def list_extensions():
    """已安装扩展及启用状态（前端加载器据此决定加载哪些插件）。"""
    return ok({"items": runtime.status_list(), "synced_at": runtime.synced_at})


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
