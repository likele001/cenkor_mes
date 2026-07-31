"""AI 平台配置与上下文（mock LLM）"""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.crud.ai_platform import (
    create_ai_gateway,
    create_ai_model,
    ensure_ai_profile,
    update_ai_global_enabled,
)
from app.services.ai.client import AiNotConfiguredError, resolve_runtime
from app.services.ai.platform_settings import gateway_row_out, get_global_settings_out


def _setup_ai(session: Session, *, api_key: str = "sk-test", model_id: str = "gpt-test"):
    update_ai_global_enabled(session, enabled=True)
    gw = create_ai_gateway(
        session,
        code="test-gw",
        display_name="测试网关",
        base_url="https://example.com/v1",
        api_key=api_key,
        is_default=True,
    )
    create_ai_model(
        session,
        gateway_id=gw.id,
        code="default",
        display_name="Test",
        model_id=model_id,
        is_default=True,
    )
    return gw


def test_ai_profile_not_enabled(session: Session):
    ensure_ai_profile(session)
    session.commit()
    with pytest.raises(AiNotConfiguredError):
        resolve_runtime(session)


def test_ai_profile_enabled(session: Session):
    _setup_ai(session)
    session.commit()
    cfg = resolve_runtime(session)
    assert cfg.model == "gpt-test"
    assert "example.com" in cfg.base_url


def test_gateway_out_masks_key(session: Session):
    gw = _setup_ai(session, api_key="secret-key")
    session.commit()
    out = gateway_row_out(gw)
    assert out["api_key_configured"] is True
    assert out["api_key"] == "******"


def test_global_settings_out(session: Session):
    update_ai_global_enabled(session, enabled=True)
    session.commit()
    out = get_global_settings_out(session)
    assert out["enabled"] is True


@patch("app.services.ai.client.chat_completion")
def test_boss_qa_mock(mock_chat, session: Session, tenant, test_user):
    from app.models.user import User

    _setup_ai(session)
    session.commit()

    mock_chat.return_value = ("今日产量正常", 10, 20)

    from app.services.ai.scenes import boss_qa

    user = session.get(User, test_user.id)
    out = boss_qa(session, tenant.id, user.id, "今天怎么样？")
    session.commit()
    assert "产量" in out["reply"] or out["reply"]


def test_build_plan_context_empty(session: Session, tenant):
    from app.services.ai.contexts.plan import build_plan_context

    assert build_plan_context(session, tenant.id, 999999) == {}


def test_build_factory_context(session: Session, tenant):
    from app.services.ai.contexts.factory import build_factory_context

    ctx = build_factory_context(session, tenant.id)
    assert "dashboard" in ctx
    assert "orders" in ctx
    assert "production_plans" in ctx
    assert "material_overview" in ctx
    assert "order_progress" in ctx


@patch("app.services.ai.scenes.chat_completion")
def test_plan_schedule_mock(mock_chat, session: Session, tenant, test_user):
    from app.models.user import User
    from app.models.order import Order, OrderItem
    from app.models.production_plan import ProductionPlan
    from app.models.customer import Customer
    from app.models.sku import Sku
    from app.models.product import Product

    customer = Customer(tenant_id=tenant.id, code="C1", name="客户", is_active=True)
    session.add(customer)
    session.flush()
    product = Product(tenant_id=tenant.id, code="P1", name="产品", is_active=True)
    session.add(product)
    session.flush()
    sku = Sku(tenant_id=tenant.id, product_id=product.id, code="S1", name="型号", is_active=True)
    session.add(sku)
    session.flush()
    order = Order(tenant_id=tenant.id, customer_id=customer.id, code="O1", status="confirmed")
    session.add(order)
    session.flush()
    session.add(OrderItem(tenant_id=tenant.id, order_id=order.id, line_no=1, sku_id=sku.id, qty=10))
    plan = ProductionPlan(
        tenant_id=tenant.id,
        order_id=order.id,
        code="PLN1",
        status="planned",
        created_by=test_user.id,
    )
    session.add(plan)
    session.flush()

    _setup_ai(session)
    session.commit()

    mock_chat.return_value = (
        '{"suggest_mode":"backward","suggest_start_date":"2026-06-01","suggest_end_date":"2026-06-10","dispatch_hints":["先派冲压"],"overload_warnings":[]}',
        10,
        20,
    )

    from app.services.ai.scenes import plan_schedule

    user = session.get(User, test_user.id)
    out = plan_schedule(session, tenant.id, user.id, plan.id)
    assert out.get("suggest_mode") == "backward" or out.get("reply")
