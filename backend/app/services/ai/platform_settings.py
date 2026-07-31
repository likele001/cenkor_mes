from sqlalchemy.orm import Session

from app.crud.ai_platform import (
    SECRET_PLACEHOLDER,
    create_ai_gateway,
    create_ai_model,
    delete_ai_gateway,
    delete_ai_model,
    ensure_ai_profile,
    get_ai_gateway_by_id,
    is_ai_globally_enabled,
    list_ai_gateways,
    list_ai_models,
    set_default_ai_gateway,
    set_default_ai_model,
    update_ai_gateway,
    update_ai_global_enabled,
    update_ai_model,
)
from app.services.ai.client import AiCallError, AiNotConfiguredError, chat_completion


def get_global_settings_out(db: Session) -> dict:
    ensure_ai_profile(db)
    return {"enabled": is_ai_globally_enabled(db)}


def gateway_row_out(g) -> dict:
    key = g.api_key or ""
    return {
        "id": g.id,
        "code": g.code,
        "display_name": g.display_name,
        "base_url": g.base_url or "",
        "api_key": SECRET_PLACEHOLDER if key else "",
        "api_key_configured": bool(key),
        "enabled": bool(g.enabled),
        "is_default": bool(g.is_default),
        "timeout_seconds": int(g.timeout_seconds or 120),
        "sort_order": int(g.sort_order or 0),
    }


def model_row_out(m) -> dict:
    return {
        "id": m.id,
        "gateway_id": m.gateway_id,
        "code": m.code,
        "display_name": m.display_name,
        "model_id": m.model_id,
        "is_vision": bool(m.is_vision),
        "is_default": bool(m.is_default),
        "is_active": bool(m.is_active),
        "sort_order": int(m.sort_order or 0),
    }


def test_connection(
    db: Session,
    *,
    gateway_id: int | None = None,
    model_code: str | None = None,
) -> dict:
    reply, _, _ = chat_completion(
        db,
        messages=[{"role": "user", "content": "回复 OK"}],
        model_code=model_code,
        gateway_id=gateway_id,
        max_tokens=16,
    )
    return {"ok": True, "reply": reply[:200]}
