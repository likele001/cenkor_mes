from app.services.production_automation import precheck_order_for_automation, precheck_plan_for_automation


def test_precheck_order_not_found(session, tenant):
    out = precheck_order_for_automation(session, tenant.id, 999999)
    assert out["ok"] is False


def test_precheck_plan_not_found(session, tenant):
    out = precheck_plan_for_automation(session, tenant.id, 999999)
    assert out["ok"] is False
