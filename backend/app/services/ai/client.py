from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from collections.abc import Iterator
from typing import NamedTuple

from app.crud.ai_platform import get_ai_gateway_by_id, get_default_ai_model, get_default_vision_model, is_ai_globally_enabled
from app.models.ai import PlatformAiGateway, PlatformAiModel
from app.services.ai.gateway_settings import get_tenant_gateway_override


class AiNotConfiguredError(Exception):
    pass


class AiCallError(Exception):
    pass


@dataclass
class AiRuntimeConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    gateway_code: str | None = None
    model_code: str | None = None


def resolve_runtime(
    db: Session,
    *,
    tenant_id: int | None = None,
    model_code: str | None = None,
    gateway_id: int | None = None,
) -> AiRuntimeConfig:
    if not is_ai_globally_enabled(db):
        raise AiNotConfiguredError("AI 未启用，请在平台总控打开总开关")

    model_row: PlatformAiModel | None = None
    if model_code:
        model_row = db.scalar(
            select(PlatformAiModel).where(PlatformAiModel.code == model_code, PlatformAiModel.is_active.is_(True))
        )
    if not model_row:
        model_row = get_default_ai_model(db)

    if not model_row:
        raise AiNotConfiguredError("请配置默认 AI 模型（在某个网关下新增模型并设为默认）")

    gw: PlatformAiGateway | None = None
    if gateway_id:
        gw = get_ai_gateway_by_id(db, gateway_id)
    else:
        gw = get_ai_gateway_by_id(db, model_row.gateway_id)

    if not gw or not gw.enabled:
        raise AiNotConfiguredError("模型所属网关不存在或未启用")

    base_url = (gw.base_url or settings.AI_BASE_URL or "").strip().rstrip("/")
    api_key = (gw.api_key or settings.AI_API_KEY or "").strip()
    timeout = int(gw.timeout_seconds or settings.AI_TIMEOUT_SECONDS or 120)
    model = (model_row.model_id or settings.AI_DEFAULT_MODEL or "").strip()
    gateway_code = gw.code
    resolved_model_code = model_row.code

    if tenant_id:
        override = get_tenant_gateway_override(db, tenant_id)
        if override:
            base_url = override["base_url"]
            api_key = override["api_key"]
            timeout = override["timeout_seconds"]
            if override.get("model_id"):
                model = override["model_id"]
            gateway_code = "tenant_override"

    if not base_url or not api_key:
        raise AiNotConfiguredError(f"请配置网关「{gw.display_name}」的 Base URL 与 API Key")
    if not model:
        raise AiNotConfiguredError("请配置模型 Model ID")

    return AiRuntimeConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
        gateway_code=gateway_code,
        model_code=resolved_model_code,
    )


def chat_completion(
    db: Session,
    *,
    tenant_id: int | None = None,
    messages: list[dict[str, str]],
    model_code: str | None = None,
    gateway_id: int | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> tuple[str, int | None, int | None]:
    cfg = resolve_runtime(db, tenant_id=tenant_id, model_code=model_code, gateway_id=gateway_id)
    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout_seconds)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except AiNotConfiguredError:
        raise
    except Exception as e:
        raise AiCallError(str(e)[:500]) from e

    choice = resp.choices[0] if resp.choices else None
    text = (choice.message.content or "").strip() if choice and choice.message else ""
    usage = resp.usage
    return (
        text,
        int(usage.prompt_tokens) if usage and usage.prompt_tokens else None,
        int(usage.completion_tokens) if usage and usage.completion_tokens else None,
    )


class StreamChunk(NamedTuple):
    delta: str
    tokens_in: int | None = None
    tokens_out: int | None = None


def chat_completion_stream(
    db: Session,
    *,
    tenant_id: int | None = None,
    messages: list[dict[str, str]],
    model_code: str | None = None,
    gateway_id: int | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> Iterator[StreamChunk]:
    cfg = resolve_runtime(db, tenant_id=tenant_id, model_code=model_code, gateway_id=gateway_id)
    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout_seconds)
        try:
            stream = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
        except TypeError:
            stream = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        for chunk in stream:
            tin: int | None = None
            tout: int | None = None
            if getattr(chunk, "usage", None):
                usage = chunk.usage
                if usage.prompt_tokens is not None:
                    tin = int(usage.prompt_tokens)
                if usage.completion_tokens is not None:
                    tout = int(usage.completion_tokens)
            if chunk.choices:
                delta = chunk.choices[0].delta.content or ""
                if delta or tin is not None or tout is not None:
                    yield StreamChunk(delta=delta, tokens_in=tin, tokens_out=tout)
            elif tin is not None or tout is not None:
                yield StreamChunk(delta="", tokens_in=tin, tokens_out=tout)
    except AiNotConfiguredError:
        raise
    except Exception as e:
        raise AiCallError(str(e)[:500]) from e


def vision_completion(
    db: Session,
    *,
    tenant_id: int | None = None,
    image_urls: list[str],
    prompt: str,
    model_code: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> tuple[str, int | None, int | None]:
    """多模态识图（OpenAI 兼容 vision）。"""
    model_row = None
    if model_code:
        from sqlalchemy import select
        from app.models.ai import PlatformAiModel

        model_row = db.scalar(
            select(PlatformAiModel).where(PlatformAiModel.code == model_code, PlatformAiModel.is_active.is_(True))
        )
    if not model_row:
        model_row = get_default_vision_model(db)
    if not model_row:
        raise AiNotConfiguredError("请配置 Vision 模型（平台 AI 模型勾选 is_vision）")

    cfg = resolve_runtime(db, tenant_id=tenant_id, model_code=model_row.code, gateway_id=model_row.gateway_id)
    content: list[dict] = [{"type": "text", "text": prompt}]
    for url in image_urls[:6]:
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})

    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=cfg.timeout_seconds)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": content}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except AiNotConfiguredError:
        raise
    except Exception as e:
        raise AiCallError(str(e)[:500]) from e

    choice = resp.choices[0] if resp.choices else None
    text = (choice.message.content or "").strip() if choice and choice.message else ""
    usage = resp.usage
    return (
        text,
        int(usage.prompt_tokens) if usage and usage.prompt_tokens else None,
        int(usage.completion_tokens) if usage and usage.completion_tokens else None,
    )
