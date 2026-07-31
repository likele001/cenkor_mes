from app.services.production_automation_settings import (
    DEFAULTS,
    get_automation_settings,
    save_automation_settings,
)


def test_get_automation_settings_defaults(session, tenant):
    data = get_automation_settings(session, tenant.id)
    assert data["enabled"] is False
    assert data["on_order_confirm"]["create_plan"] is False
    assert data["briefing"]["mode"] == "rule"


def test_save_automation_settings_merge(session, tenant):
    save_automation_settings(session, tenant.id, {"enabled": True, "on_order_confirm": {"create_plan": True}})
    session.commit()
    data = get_automation_settings(session, tenant.id)
    assert data["enabled"] is True
    assert data["on_order_confirm"]["create_plan"] is True
    assert data["on_plan_saved"]["auto_dispatch"] is False
