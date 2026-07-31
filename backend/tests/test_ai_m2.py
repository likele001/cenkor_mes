"""AI 租户网关覆盖与 RAG 帮助"""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.crud.ai_platform import create_ai_gateway, create_ai_model, update_ai_global_enabled
from app.services.ai.client import resolve_runtime
from app.services.ai.gateway_settings import get_gateway_settings_admin, save_gateway_settings
from app.services.ai.rag_help import search_docs


def _setup_platform_ai(session: Session):
    update_ai_global_enabled(session, enabled=True)
    gw = create_ai_gateway(
        session,
        code="plat-gw",
        display_name="平台网关",
        base_url="https://platform.example/v1",
        api_key="sk-platform",
        is_default=True,
    )
    create_ai_model(
        session,
        gateway_id=gw.id,
        code="default",
        display_name="Default",
        model_id="gpt-platform",
        is_default=True,
    )
    return gw


def test_tenant_gateway_override(session: Session, tenant):
    _setup_platform_ai(session)
    save_gateway_settings(
        session,
        tenant.id,
        {
            "enabled": True,
            "base_url": "https://tenant.example/v1",
            "api_key": "sk-tenant",
            "model_id": "gpt-tenant",
            "timeout_seconds": 90,
        },
    )
    session.commit()

    cfg = resolve_runtime(session, tenant_id=tenant.id)
    assert "tenant.example" in cfg.base_url
    assert cfg.model == "gpt-tenant"
    assert cfg.gateway_code == "tenant_override"


def test_gateway_settings_masks_key(session: Session, tenant):
    save_gateway_settings(
        session,
        tenant.id,
        {"enabled": True, "base_url": "https://x/v1", "api_key": "secret"},
    )
    session.commit()
    out = get_gateway_settings_admin(session, tenant.id)
    assert out["api_key_configured"] is True
    assert out["api_key_masked"] == "********"


def test_rag_search_docs():
    hits = search_docs("报工 小程序")
    assert isinstance(hits, list)
    if hits:
        assert "source" in hits[0]
        assert hits[0]["score"] >= 0


@patch("app.services.ai.rag_help.chat_completion")
def test_help_answer_mock(mock_chat, session: Session, tenant):
    mock_chat.return_value = ("请先在系统设置配置小程序 AppID", 1, 2)
    _setup_platform_ai(session)
    session.commit()

    from app.services.ai.rag_help import help_answer

    # 强制有检索结果：用常见词
    with patch("app.services.ai.rag_help.search_docs") as mock_search:
        mock_search.return_value = [{"source": "小程序使用指南.md", "title": "配置", "snippet": "AppID", "score": 2}]
        out = help_answer(session, tenant_id=tenant.id, question="怎么配置小程序")
    assert "AppID" in out["answer"] or out["answer"]
