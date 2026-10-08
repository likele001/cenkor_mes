# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""平台 AI 配置层路由（波次 0）：网关 / 模型 / 总开关 / Prompt / 连通性测试。

挂载前缀：/api/ai（匹配前端 src/api/ai.ts 契约）。
仅提供「配置管道」，不含 AI 业务算法；业务端点（chat/plan/deep/alerts）留波次 2。
单租户：/gateway-settings 直接读写 PlatformAiProfile（总开关 + 兜底 base_url/api_key/timeout）。

安全：api_key 一律掩码回显（SECRET_MASK），GET 永不返回明文；PUT 收到掩码或空则不改。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud import ai_platform as crud_ai
from app.crud import platform_setting as crud_ps
from app.models.user import User
from app.schemas.ai import (
    AiGatewaySettingsIn,
    AiPromptSettingsIn,
    AiTestIn,
    PlatformAiGatewayIn,
    PlatformAiGatewayUpdateIn,
    PlatformAiModelIn,
    PlatformAiModelUpdateIn,
)

router = APIRouter()

SECRET_MASK = "********"
PROMPT_KEY = "ai.system_prompt"
PROMPT_MAX_LEN = 2000

# 配置管理需 AI 使用 + 系统设置权限；纯读取模型列表仅需 AI 使用权限
MANAGE = require_permissions(["ai.use", "setting.manage"])
USE = require_permissions(["ai.use"])


def _mask(key: str | None) -> str:
    return SECRET_MASK if (key or "").strip() else ""


def _gateway_out(g) -> dict:
    return {
        "id": g.id,
        "code": g.code,
        "display_name": g.display_name,
        "base_url": g.base_url,
        "api_key_configured": bool((g.api_key or "").strip()),
        "api_key_masked": _mask(g.api_key),
        "enabled": g.enabled,
        "is_default": g.is_default,
        "timeout_seconds": g.timeout_seconds,
        "sort_order": g.sort_order,
    }


def _model_out(m) -> dict:
    return {
        "id": m.id,
        "gateway_id": m.gateway_id,
        "code": m.code,
        "display_name": m.display_name,
        "model_id": m.model_id,
        "is_vision": m.is_vision,
        "is_default": m.is_default,
        "is_active": m.is_active,
        "sort_order": m.sort_order,
    }


# ── 总开关 + 兜底配置（PlatformAiProfile）─────────────────────────────


@router.get("/gateway-settings", dependencies=[Depends(MANAGE)])
def get_gateway_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = crud_ai.ensure_ai_profile(db)
    db.commit()
    return ok(
        {
            "enabled": bool(p.enabled),
            "base_url": p.base_url or "",
            "api_key_configured": bool((p.api_key or "").strip()),
            "api_key_masked": _mask(p.api_key),
            "timeout_seconds": int(p.timeout_seconds or 120),
        }
    )


@router.put("/gateway-settings", dependencies=[Depends(MANAGE)])
def save_gateway_settings(
    payload: AiGatewaySettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = crud_ai.ensure_ai_profile(db)
    data = payload.model_dump(exclude_none=True)
    if "enabled" in data:
        p.enabled = bool(data["enabled"])
    if "base_url" in data:
        p.base_url = str(data["base_url"]).strip().rstrip("/")
    if "timeout_seconds" in data:
        p.timeout_seconds = max(10, min(600, int(data["timeout_seconds"])))
    if "api_key" in data:
        k = str(data["api_key"]).strip()
        if k and k != SECRET_MASK:
            p.api_key = k
        elif k == "":
            p.api_key = None
    db.commit()
    return ok(
        {
            "enabled": bool(p.enabled),
            "base_url": p.base_url or "",
            "api_key_configured": bool((p.api_key or "").strip()),
            "api_key_masked": _mask(p.api_key),
            "timeout_seconds": int(p.timeout_seconds or 120),
        }
    )


# ── 网关 CRUD ────────────────────────────────────────────────────────


@router.get("/gateways", dependencies=[Depends(MANAGE)])
def list_gateways(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = crud_ai.list_ai_gateways(db)
    return ok({"items": [_gateway_out(g) for g in rows]})


@router.post("/gateways", dependencies=[Depends(MANAGE)])
def create_gateway(
    payload: PlatformAiGatewayIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if crud_ai.get_ai_gateway_by_code(db, payload.code.strip()):
        raise HTTPException(status_code=400, detail="网关 code 已存在")
    row = crud_ai.create_ai_gateway(
        db,
        code=payload.code,
        display_name=payload.display_name,
        base_url=payload.base_url,
        api_key=payload.api_key,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        sort_order=payload.sort_order,
        is_default=payload.is_default,
    )
    db.commit()
    return ok(_gateway_out(row))


@router.put("/gateways/{gateway_id}", dependencies=[Depends(MANAGE)])
def update_gateway(
    gateway_id: int,
    payload: PlatformAiGatewayUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = crud_ai.get_ai_gateway_by_id(db, gateway_id)
    if not row:
        raise HTTPException(status_code=404, detail="网关不存在")
    fields = payload.model_dump(exclude_none=True)
    code = fields.get("code")
    if code and code.strip() != row.code:
        if crud_ai.get_ai_gateway_by_code(db, code.strip()):
            raise HTTPException(status_code=400, detail="网关 code 已存在")
    crud_ai.update_ai_gateway(db, row, **fields)
    db.commit()
    return ok(_gateway_out(row))


@router.delete("/gateways/{gateway_id}", dependencies=[Depends(MANAGE)])
def delete_gateway(gateway_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = crud_ai.get_ai_gateway_by_id(db, gateway_id)
    if not row:
        raise HTTPException(status_code=404, detail="网关不存在")
    models = crud_ai.list_ai_models(db, gateway_id=gateway_id)
    if models:
        raise HTTPException(status_code=400, detail="该网关下仍有模型，请先删除模型")
    crud_ai.delete_ai_gateway(db, row)
    db.commit()
    return ok({"ok": True})


@router.post("/gateways/{gateway_id}/set-default", dependencies=[Depends(MANAGE)])
def set_default_gateway(gateway_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = crud_ai.get_ai_gateway_by_id(db, gateway_id)
    if not row:
        raise HTTPException(status_code=404, detail="网关不存在")
    crud_ai.set_default_ai_gateway(db, row)
    db.commit()
    return ok(_gateway_out(row))


# ── 模型 CRUD ────────────────────────────────────────────────────────


@router.get("/models", dependencies=[Depends(USE)])
def list_models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """运行时模型选择器（匹配前端 ai.ts listModels）：仅启用的非 vision 模型。"""
    rows = [m for m in crud_ai.list_ai_models(db) if m.is_active and not m.is_vision]
    return ok(
        {
            "items": [
                {"code": m.code, "display_name": m.display_name, "is_default": m.is_default, "model_id": m.model_id}
                for m in rows
            ]
        }
    )


@router.get("/model-entries", dependencies=[Depends(MANAGE)])
def list_model_entries(
    gateway_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """管理页用：完整模型条目（含 vision/停用），可按网关过滤。"""
    rows = crud_ai.list_ai_models(db, gateway_id=gateway_id)
    return ok({"items": [_model_out(m) for m in rows]})


@router.post("/models", dependencies=[Depends(MANAGE)])
def create_model(
    payload: PlatformAiModelIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud_ai.get_ai_gateway_by_id(db, payload.gateway_id):
        raise HTTPException(status_code=400, detail="所属网关不存在")
    exists = [m for m in crud_ai.list_ai_models(db, gateway_id=payload.gateway_id) if m.code == payload.code.strip()]
    if exists:
        raise HTTPException(status_code=400, detail="同一网关下模型 code 已存在")
    row = crud_ai.create_ai_model(
        db,
        gateway_id=payload.gateway_id,
        code=payload.code,
        display_name=payload.display_name,
        model_id=payload.model_id,
        is_vision=payload.is_vision,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        is_default=payload.is_default,
    )
    db.commit()
    return ok(_model_out(row))


@router.put("/models/{model_id}", dependencies=[Depends(MANAGE)])
def update_model(
    model_id: int,
    payload: PlatformAiModelUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = crud_ai.get_ai_model_by_id(db, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    fields = payload.model_dump(exclude_none=True)
    crud_ai.update_ai_model(db, row, **fields)
    db.commit()
    return ok(_model_out(row))


@router.delete("/models/{model_id}", dependencies=[Depends(MANAGE)])
def delete_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = crud_ai.get_ai_model_by_id(db, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    crud_ai.delete_ai_model(db, row)
    db.commit()
    return ok({"ok": True})


@router.post("/models/{model_id}/set-default", dependencies=[Depends(MANAGE)])
def set_default_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = crud_ai.get_ai_model_by_id(db, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    crud_ai.set_default_ai_model(db, row)
    db.commit()
    return ok(_model_out(row))


# ── Prompt 设置（存 PlatformSetting，供波次 2 对话使用）────────────────


@router.get("/prompt-settings", dependencies=[Depends(MANAGE)])
def get_prompt_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    val = crud_ps.get_setting(db, PROMPT_KEY) or ""
    return ok({"prompt": str(val).strip()[:PROMPT_MAX_LEN], "max_length": PROMPT_MAX_LEN})


@router.put("/prompt-settings", dependencies=[Depends(MANAGE)])
def save_prompt_settings(
    payload: AiPromptSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = (payload.prompt or "").strip()[:PROMPT_MAX_LEN]
    crud_ps.set_setting(db, PROMPT_KEY, text or None)
    db.commit()
    return ok({"prompt": text, "max_length": PROMPT_MAX_LEN})


# ── 连通性测试 ───────────────────────────────────────────────────────


@router.post("/test-connection", dependencies=[Depends(MANAGE)])
def test_connection(
    payload: AiTestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """用当前（或指定）网关+模型跑一次最小对话，验证 key/url/model 可用。"""
    from app.services.ai.client import AiCallError, AiNotConfiguredError, chat_completion

    try:
        text, tin, tout = chat_completion(
            db,
            messages=[{"role": "user", "content": "ping"}],
            model_code=payload.model_code,
            gateway_id=payload.gateway_id,
            max_tokens=8,
        )
        return ok({"ok": True, "reply": text[:200], "tokens_in": tin, "tokens_out": tout})
    except AiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AiCallError as e:
        raise HTTPException(status_code=502, detail=str(e))
