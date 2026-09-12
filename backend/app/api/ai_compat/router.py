# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""独立版兼容层 - AI 智能中心占位接口。

为了确保开源独立版不出现 /api/ai/* 红色 404，这里提供三个安全占位路由，
无论是否登录均返回空数据。前端在独立版默认不展示 AI 区块，这些路由仅作为兜底。
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/brief", summary="独立版 AI 简报（占位）")
async def ai_brief():
    """独立版无 AI 简报，统一返回空内容。前端首页已禁用 AI 区块。"""
    return {"mode": None, "content": None, "available": False}


@router.get("/alerts", summary="独立版 AI 异常告警列表（占位）")
async def ai_alerts_list():
    """独立版无 AI 告警，统一返回空列表。"""
    return {"items": [], "available": False}


@router.post("/alerts/run", summary="独立版 AI 异常告警扫描（占位）")
async def ai_alerts_run():
    """独立版无 AI 告警扫描，返回空结果。"""
    return {"events": 0, "notified": 0, "available": False}
