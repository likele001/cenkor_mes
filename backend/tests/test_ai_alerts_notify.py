"""AI 预警通知：create_todo_on_critical"""

from datetime import datetime
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.ai import AiAlertEvent
from app.services.ai.alerts import notify_pending_alerts


def test_notify_critical_creates_todo(session: Session, tenant):
    ev = AiAlertEvent(
        tenant_id=tenant.id,
        rule_code="order_overdue",
        level="danger",
        title="逾期订单 2 笔",
        summary="测试",
        dedupe_key="test:todo",
    )
    session.add(ev)
    session.flush()

    with patch("app.services.ai.alerts.notify_users_with_permission") as mock_notify:
        n = notify_pending_alerts(
            session,
            tenant.id,
            alert_prefs={"notify_on_scan": False, "create_todo_on_critical": True},
        )
        assert n == 1
        assert mock_notify.call_count == 1
        kwargs = mock_notify.call_args.kwargs
        assert kwargs["permission_code"] == "plan.manage"
        assert kwargs["biz_type"] == "todo"
        assert "[待办]" in kwargs["title"]

    ev2 = session.get(AiAlertEvent, ev.id)
    assert ev2 is not None
    assert ev2.notified_at is not None


def test_notify_on_scan_only_warning_no_todo(session: Session, tenant):
    ev = AiAlertEvent(
        tenant_id=tenant.id,
        rule_code="yield_drop",
        level="warning",
        title="良率下降",
        summary="测试",
        dedupe_key="test:warn",
    )
    session.add(ev)
    session.flush()

    with patch("app.services.ai.alerts.notify_users_with_permission") as mock_notify:
        n = notify_pending_alerts(
            session,
            tenant.id,
            alert_prefs={"notify_on_scan": True, "create_todo_on_critical": True},
        )
        assert n == 1
        assert mock_notify.call_count == 1
        assert mock_notify.call_args.kwargs["biz_type"] == "ai_alert"
