from app.services.ai.alert_settings import get_alert_thresholds, save_alert_thresholds


def test_alert_thresholds_default(session, tenant):
    t = get_alert_thresholds(session, tenant.id)
    assert t["pending_audit"] == 50
    assert t["yield_drop_delta"] == 0.05


def test_alert_thresholds_save(session, tenant):
    save_alert_thresholds(session, tenant.id, {"pending_audit": 80})
    session.commit()
    t = get_alert_thresholds(session, tenant.id)
    assert t["pending_audit"] == 80
