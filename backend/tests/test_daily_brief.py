from unittest.mock import patch

from app.services.daily_brief import build_rule_brief, get_live_brief


def test_build_rule_brief():
    text = build_rule_brief({"date": "2026-05-25", "today": {"good_qty": 10}, "pending_audit": 2, "overdue_orders": 1})
    assert "2026-05-25" in text
    assert "10" in text


def test_get_live_brief_rule(session, tenant):
    data = get_live_brief(session, tenant.id)
    assert data["mode"] in ("rule", "llm")
    assert "content" in data
