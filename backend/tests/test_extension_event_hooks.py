# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""报工提交端点的事件钩子测试：拦截否决 → 400 无脏数据；通知 emit 位置与 payload。

说明：直接调 API 函数（仓库惯例）。鉴权辅助（_ensure_report_submit）与
批量端点的槽位同步（sync_assignment_units，见「批量模式守卫」既有缺陷——
端点无条件建 draft 槽位后又被 count_draft_units>0 拦截）与钩子无关，
用 monkeypatch 旁路以聚焦钩子行为。
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.api.h5 import report_units as unit_module
from app.api.h5 import tasks as tasks_module
from app.api.h5.report_units import ReportUnitSubmitIn, submit_report_unit_api
from app.api.h5.tasks import submit_report_api
from app.extension_host.events import InterceptDecision, event_bus
from app.extension_host.loader import mount_extensions
from app.extension_host.state import runtime
from app.models.report import Report
from app.models.report_unit import ReportUnit


@pytest.fixture(autouse=True)
def _isolate_runtime():
    """runtime.reset() 联动清空总线订阅。"""
    runtime.reset()
    yield
    runtime.reset()


def _fake_install(*keys: str) -> None:
    for key in keys:
        runtime.installed[key] = {"manifest": None, "path": "."}


@pytest.fixture
def batch_ready(monkeypatch: pytest.MonkeyPatch):
    """批量报工端点可达所需的旁路（鉴权 + 槽位同步守卫）。"""
    monkeypatch.setattr(tasks_module, "_ensure_report_submit", lambda user: None)
    monkeypatch.setattr(tasks_module, "sync_assignment_units", lambda db, a: None)


# ── 14. 批量报工被拦截 → 400 + 无脏数据 ──


def test_submit_report_intercept_rejects(batch_ready, session, test_user, task, assignment):
    _fake_install("quality_guard")
    event_bus.subscribe_intercept(
        "quality_guard", "report.submitting",
        lambda ev: InterceptDecision(allow=False, reason="不良率超阈值"))

    # 嵌套 savepoint：否决后回滚到调用前，模拟真实请求的「无 commit 即丢弃」
    sp = session.begin_nested()
    with pytest.raises(HTTPException) as ei:
        submit_report_api(
            task_code=task.task_code, good_qty=5, bad_qty=1,
            remark=None, attachment_ids=None, db=session, user=test_user)
    sp.rollback()

    assert ei.value.status_code == 400
    assert "quality_guard" in ei.value.detail
    assert "不良率超阈值" in ei.value.detail
    assert session.scalar(select(func.count(Report.id))) == 0


def test_submit_report_intercept_fail_open_passes(batch_ready, session, test_user, task, assignment):
    """拦截 handler 抛异常 → fail-open，报工正常走完。"""
    _fake_install("ext_broken")

    def boom(ev):
        raise RuntimeError("扩展内部错误")

    event_bus.subscribe_intercept("ext_broken", "report.submitting", boom)
    out = submit_report_api(
        task_code=task.task_code, good_qty=5, bad_qty=0,
        remark=None, attachment_ids=None, db=session, user=test_user)
    assert out["code"] == 200
    assert session.scalar(select(func.count(Report.id))) == 1


# ── 15. 单件报工被拦截 → 400 + 无脏数据 ──


def test_submit_report_unit_intercept_rejects(
        monkeypatch: pytest.MonkeyPatch, session, test_user, task, assignment):
    monkeypatch.setattr(unit_module, "_ensure_report_submit", lambda user: None)
    monkeypatch.setattr(unit_module, "use_unit_report_mode", lambda db: True)
    monkeypatch.setattr(unit_module, "auto_bind_piece_to_unit", lambda db, unit, t: None)

    _fake_install("hr_ext")
    event_bus.subscribe_intercept(
        "hr_ext", "report_unit.submitting",
        lambda ev: InterceptDecision(allow=False, reason="未完成安全培训"))

    payload_in = ReportUnitSubmitIn(
        task_code=task.task_code, unit_seq=None, result_type="good",
        attachment_ids="1", remark=None, anomaly_confirmed=False)
    sp = session.begin_nested()
    with pytest.raises(HTTPException) as ei:
        submit_report_unit_api(payload_in, db=session, user=test_user)
    sp.rollback()

    assert ei.value.status_code == 400
    assert "hr_ext" in ei.value.detail
    submitted = session.scalar(
        select(func.count(ReportUnit.id)).where(ReportUnit.status == "submitted"))
    assert submitted == 0


# ── 16. 通知 emit：位置（commit 前注册）与 payload ──


def test_submit_report_emits_after_commit(batch_ready, monkeypatch: pytest.MonkeyPatch,
                                          session, test_user, task, assignment):
    """monkeypatch 记录器替代 emit_after_commit：断言事件名/payload/actor，不真分发。"""
    calls: list[tuple] = []

    def recorder(db, event_name, payload, **kw):
        assert db is session  # 必须在 commit 前带着 session 注册
        calls.append((event_name, payload, kw.get("actor_id")))

    monkeypatch.setattr(event_bus, "emit_after_commit", recorder)
    out = submit_report_api(
        task_code=task.task_code, good_qty=8, bad_qty=2,
        remark="钩子测试", attachment_ids=None, db=session, user=test_user)
    assert out["code"] == 200

    assert len(calls) == 1
    name, payload, actor_id = calls[0]
    assert name == "report.submitted"
    assert actor_id == test_user.id
    assert payload["task_id"] == task.id
    assert payload["task_code"] == task.task_code
    assert payload["report_user_id"] == test_user.id
    assert payload["good_qty"] == 8 and payload["bad_qty"] == 2
    assert payload["remark"] == "钩子测试"
    report_id = session.scalar(select(Report.id))
    assert payload["report_id"] == report_id


def test_submit_report_unit_emits_after_commit(
        monkeypatch: pytest.MonkeyPatch, session, test_user, task, assignment):
    monkeypatch.setattr(unit_module, "_ensure_report_submit", lambda user: None)
    monkeypatch.setattr(unit_module, "use_unit_report_mode", lambda db: True)
    monkeypatch.setattr(unit_module, "auto_bind_piece_to_unit", lambda db, unit, t: None)

    calls: list[tuple] = []
    monkeypatch.setattr(
        event_bus, "emit_after_commit",
        lambda db, name, payload, **kw: calls.append((name, payload, kw.get("actor_id"))))

    payload_in = ReportUnitSubmitIn(
        task_code=task.task_code, unit_seq=None, result_type="good",
        attachment_ids="1", remark=None, anomaly_confirmed=True)
    out = submit_report_unit_api(payload_in, db=session, user=test_user)
    assert out["code"] == 200

    assert len(calls) == 1
    name, payload, actor_id = calls[0]
    assert name == "report_unit.submitted"
    assert actor_id == test_user.id
    assert payload["task_code"] == task.task_code
    assert payload["result_type"] == "good"
    assert payload["user_id"] == test_user.id
    assert payload["anomaly_confirmed"] is True
    assert payload["report_unit_id"] == session.scalar(
        select(ReportUnit.id).where(ReportUnit.status == "submitted"))


# ── 17. hook_demo 样例：真 commit → 通知 handler 写扩展自有表 ──

HOOK_DEMO_DIR = Path(__file__).resolve().parents[1] / "extensions_samples" / "hook_demo"


def test_hook_demo_sample_writes_own_table(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """copytree 样例 → mount 订阅 → 真 commit 触发 report.submitted → 自有表出现统计行。

    跨线程 + SQLite：用「文件库」而非 :memory:，让 handler 的 open_session（另一线程、
    另一连接，文件库默认 NullPool 每线程新连接）与测试主线程看到同一份数据。
    session_factory 用 monkeypatch 注入并自动还原，不污染其他用例。
    """
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    shutil.copytree(HOOK_DEMO_DIR, ext_dir / "hook_demo")

    engine = create_engine(f"sqlite:///{tmp_path / 'hook.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE ext_hook_demo_report_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, task_code VARCHAR(64), "
            "report_id INTEGER, good_qty INTEGER, bad_qty INTEGER, logged_at DATETIME)"))
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(event_bus, "session_factory", TestSession)

    app = FastAPI()
    mount_extensions(app, ext_dir, auth_dependencies=[])
    assert "hook_demo" in runtime.installed
    assert runtime.is_enabled("hook_demo")

    db = TestSession()
    db.execute(text("SELECT 1"))  # 开一个事务，确保走 after_commit 分支而非立即分发
    event_bus.emit_after_commit(db, "report.submitted", {
        "report_id": 77, "task_id": 9, "task_code": "T-077",
        "report_user_id": 5, "good_qty": 12, "bad_qty": 3, "remark": "料废",
    }, actor_id=5)
    db.commit()
    db.close()
    assert event_bus.wait_pending(5.0)

    with TestSession() as s:
        rows = s.execute(text(
            "SELECT task_code, report_id, good_qty, bad_qty FROM ext_hook_demo_report_log")).all()
    assert rows == [("T-077", 77, 12, 3)]
    engine.dispose()
