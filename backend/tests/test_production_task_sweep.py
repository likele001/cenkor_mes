# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""production.automation.pipeline 定时无参调用的兜底扫描测试"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.production_plan import ProductionPlan
from app.services import production_automation as pa
from app.tasks.production import _run_scheduled_sweep, production_automation_pipeline


def _add_plan(session: Session, order_id: int, code: str, start_date, status="planned", created_by=None):
    p = ProductionPlan(
        order_id=order_id, code=code, status=status, start_date=start_date, created_by=created_by,
    )
    session.add(p)
    session.flush()
    return p


def test_sweep_empty(session):
    out = _run_scheduled_sweep(session, today=date.today())

    assert out["ok"] is True
    assert out["swept"] == 0


def test_sweep_runs_only_due_planned(session, order_item, test_user, monkeypatch):
    order, _ = order_item
    due = _add_plan(session, order.id, "PP-SWEEP-1", date.today() - timedelta(days=1), created_by=test_user.id)
    _add_plan(session, order.id, "PP-SWEEP-2", date.today() + timedelta(days=3))
    _add_plan(session, order.id, "PP-SWEEP-3", date.today() - timedelta(days=1), status="in_progress")
    session.commit()

    calls = []

    def fake_pipeline(db, plan_id, user_id, **kwargs):
        calls.append((plan_id, user_id, kwargs.get("trigger")))
        return {"steps": ["schedule"]}

    monkeypatch.setattr(pa, "run_schedule_pipeline", fake_pipeline)

    out = _run_scheduled_sweep(session, today=date.today())

    assert [c[0] for c in calls] == [due.id]
    assert calls[0][1] == test_user.id
    assert calls[0][2] == "cron"
    assert out["swept"] == 1
    assert out["results"][0]["ok"] is True


def test_sweep_continues_after_failure(session, order_item, test_user, monkeypatch):
    order, _ = order_item
    p1 = _add_plan(session, order.id, "PP-SWEEP-4", date.today(), created_by=test_user.id)
    p2 = _add_plan(session, order.id, "PP-SWEEP-5", date.today())
    session.commit()

    def fake_pipeline(db, plan_id, user_id, **kwargs):
        if plan_id == p1.id:
            raise ValueError("BOM 缺失")
        return {"steps": ["schedule"]}

    monkeypatch.setattr(pa, "run_schedule_pipeline", fake_pipeline)

    out = _run_scheduled_sweep(session, today=date.today())

    assert out["swept"] == 2
    assert out["results"][0] == {"plan_id": p1.id, "ok": False, "error": "BOM 缺失"}
    assert out["results"][1]["ok"] is True


def test_task_dispatches_sweep_when_no_plan_id(monkeypatch):
    import app.tasks.production as tp

    captured = {}

    def fake_sweep(db, *, trigger="cron", today=None):
        captured["trigger"] = trigger
        return {"ok": True, "swept": 0, "results": []}

    monkeypatch.setattr(tp, "_run_scheduled_sweep", fake_sweep)

    out = production_automation_pipeline(plan_id=None)

    assert out["ok"] is True
    assert captured["trigger"] == "cron"


def test_task_still_accepts_explicit_plan(monkeypatch):
    import app.tasks.production as tp
    import app.services.production_automation_settings as pas

    calls = []

    def fake_sweep(db, *, trigger="cron", today=None):
        calls.append("sweep")
        return {}

    monkeypatch.setattr(tp, "_run_scheduled_sweep", fake_sweep)
    # 该函数内部自建 SessionLocal 连独立空库，get_automation_settings 会查不存在的表抛
    # 异常，导致 run_schedule_pipeline 不被调用。本测试聚焦调度逻辑，隔离 settings 的 DB 依赖。
    monkeypatch.setattr(
        pas, "get_automation_settings", lambda db, tenant_id=1: {"on_plan_saved": {}}
    )
    monkeypatch.setattr(
        pa,
        "run_schedule_pipeline",
        lambda db, plan_id, user_id, **kwargs: calls.append((plan_id, user_id)),
    )

    production_automation_pipeline(plan_id=42, user_id=9, trigger="plan_saved")

    assert calls == [(42, 9)]
