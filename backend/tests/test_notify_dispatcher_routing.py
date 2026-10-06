# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""分发器路由规则测试：规则开关必须真的生效，认不出的事件码必须留下痕迹。

守的是两类静默失败：
- `rules[event].enabled = false` 以前只是界面状态，分发器从不读它；
- 事件码不在任何分类里时 `dispatch()` 直接 return 0，配了规则也一条不发、日志零条。
"""
import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.tenant_setting import upsert_setting
from app.models.feishu_push_log import FeishuPushLog
from app.models.user import User
from app.services.feishu.settings import EVENT_CATALOG
from app.services.notify_channels import KNOWN_EVENTS
from app.services.notify_dispatcher import dispatch


@pytest.fixture
def bound_user(session: Session, test_user: User) -> User:
    test_user.feishu_open_id = "ou_bound_001"
    session.flush()
    return test_user


def _enable(session: Session, rules: dict[str, Any]) -> None:
    upsert_setting(session, "feishu.notify", json.dumps({
        "enabled": True,
        "app_id": "cli_a",
        "app_secret": "secret",
        "rules": rules,
        "groups": [
            {"code": "management", "name": "管理群", "enabled": True,
             "channels": {"feishu": {"chat_id": "oc_mgmt", "enabled": True}}},
        ],
    }, ensure_ascii=False))
    session.flush()


def _logs(session: Session, event_code: str) -> list[FeishuPushLog]:
    return list(session.scalars(
        select(FeishuPushLog).where(FeishuPushLog.event_code == event_code)
    ).all())


# ── 规则开关 ──

def test_personal_event_pushes_when_rule_enabled(session: Session, bound_user):
    """对照用例：开关开着时必须真的产出一条待推送 log。"""
    _enable(session, {"report.rejected": {"enabled": True, "targets": ["assigned_employee"]}})
    created = dispatch(
        session, "report.rejected",
        title="报工被驳回", content="请查看", user_id=bound_user.id,
    )
    assert created == 1
    assert _logs(session, "report.rejected")[0].target_ref == "ou_bound_001"


def test_personal_event_suppressed_when_rule_disabled(session: Session, bound_user):
    """关掉这条规则后一条都不能发（此前 enabled 从不被读取）。"""
    _enable(session, {"report.rejected": {"enabled": False, "targets": ["assigned_employee"]}})
    created = dispatch(
        session, "report.rejected",
        title="报工被驳回", content="请查看", user_id=bound_user.id,
    )
    assert created == 0
    assert _logs(session, "report.rejected") == []


def test_group_event_suppressed_when_rule_disabled(session: Session):
    _enable(session, {"brief.daily": {"enabled": False, "targets": ["group:management"]}})
    created = dispatch(session, "brief.daily", title="今日简报", content="产线 A")
    assert created == 0
    assert _logs(session, "brief.daily") == []


# ── 认不出的事件码 ──

def test_unknown_event_with_rule_leaves_visible_log(session: Session):
    """有人在管理端配过规则却不认识的事件码，必须留下可查的失败记录。"""
    _enable(session, {"order.confirmed": {"enabled": True, "targets": ["group:management"]}})
    created = dispatch(
        session, "order.confirmed", title="订单已确认", content="SO-1",
        biz_type="order", biz_id=7,
    )
    assert created == 0
    rows = _logs(session, "order.confirmed")
    assert len(rows) == 1
    assert rows[0].status == "skipped"
    assert "未注册推送分类" in rows[0].error_msg
    assert rows[0].biz_id == 7


def test_unknown_event_without_rule_stays_silent(session: Session):
    """没配过规则的事件（调用方只要站内信）不该刷屏产出记录。"""
    _enable(session, {})
    created = dispatch(session, "order.shipped", title="已发货", content="SO-2")
    assert created == 0
    assert _logs(session, "order.shipped") == []


# ── 目录与分类不许漂移 ──

def test_event_catalog_matches_registered_categories():
    """界面能配规则的事件，分发器必须都认识，否则就是「配了不发」。"""
    catalog = {e["code"] for e in EVENT_CATALOG}
    assert catalog == set(KNOWN_EVENTS), (
        f"仅在目录: {sorted(catalog - set(KNOWN_EVENTS))} / 仅在分类: {sorted(set(KNOWN_EVENTS) - catalog)}"
    )
