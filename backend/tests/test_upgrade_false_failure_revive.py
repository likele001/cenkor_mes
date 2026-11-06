# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""重启误判复核：服务其实已恢复，任务不该永远挂着 failed。

覆盖 2026-11-06 实测的坑：同版本升级停机 684 秒后服务自己起来了，
reconcile 在端口刚绑住那一瞬探健康拿到「无响应」，把任务判成 failed，
而此后再也没有任何代码会复查它。
"""
from datetime import datetime, timedelta

import pytest

from app.models.upgrade_job import UpgradeJob
from app.services import upgrade_service

RESTART_FAIL = "重启后健康校验失败：期望 v2.2.14，实际 无响应；请查看升级日志，必要时执行回滚"


def _make_job(session, **overrides):
    fields = {
        "action": "upgrade",
        "from_version": "v2.2.13",
        "to_version": "v2.2.14",
        "status": "failed",
        "stage": "done",
        "error": RESTART_FAIL,
        "started_at": datetime.now() - timedelta(minutes=12),
        "finished_at": datetime.now(),
    }
    fields.update(overrides)
    job = UpgradeJob(**fields)
    session.add(job)
    session.flush()
    return job


@pytest.fixture
def healthy_at_target(monkeypatch):
    """模拟「服务已恢复到目标版本」：本地 VERSION 与 /api/health 都是 v2.2.14。"""
    monkeypatch.setattr(upgrade_service, "read_local_version", lambda: "v2.2.14")
    monkeypatch.setattr(
        upgrade_service, "_probe_health", lambda timeout=5.0: {"status": "ok", "version": "v2.2.14"}
    )
    monkeypatch.setattr(upgrade_service, "_log", lambda job_id, msg: None)


def test_revives_when_running_version_matches_target(session, healthy_at_target):
    job = _make_job(session)
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "success"
    assert job.stage == "done"
    # 原判原因要保留，便于审计
    assert job.error.startswith("[已复核]")
    assert "重启后健康校验失败" in job.error
    assert "改判为成功" in job.error


def test_keeps_failed_when_health_version_mismatch(session, monkeypatch):
    monkeypatch.setattr(upgrade_service, "read_local_version", lambda: "v2.2.14")
    monkeypatch.setattr(
        upgrade_service, "_probe_health", lambda timeout=5.0: {"status": "ok", "version": "v2.2.13"}
    )
    monkeypatch.setattr(upgrade_service, "_log", lambda job_id, msg: None)
    job = _make_job(session)
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"
    assert job.error == RESTART_FAIL


def test_keeps_failed_when_service_unreachable(session, monkeypatch):
    monkeypatch.setattr(upgrade_service, "read_local_version", lambda: "v2.2.14")
    monkeypatch.setattr(upgrade_service, "_probe_health", lambda timeout=5.0: None)
    monkeypatch.setattr(upgrade_service, "_log", lambda job_id, msg: None)
    job = _make_job(session)
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"


def test_keeps_failed_when_local_version_not_switched(session, healthy_at_target, monkeypatch):
    """代码没换过去（本地仍是旧版）时，健康探测对上也不能改判。"""
    monkeypatch.setattr(upgrade_service, "read_local_version", lambda: "v2.2.13")
    job = _make_job(session)
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"


def test_ignores_non_restart_failure(session, healthy_at_target):
    """依赖装不上之类的真实失败，绝不能因为版本恰好对就洗白。"""
    job = _make_job(session, error="依赖安装失败：pip 返回非 0")
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"
    assert job.error == "依赖安装失败：pip 返回非 0"


def test_ignores_stale_jobs_outside_window(session, healthy_at_target):
    job = _make_job(session, finished_at=datetime.now() - timedelta(hours=48))
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"


def test_rollback_job_becomes_rolled_back(session, healthy_at_target):
    job = _make_job(session, action="rollback", to_version="v2.2.14")
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "rolled_back"


def test_ignores_job_not_in_done_stage(session, healthy_at_target):
    job = _make_job(session, stage="restart")
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "failed"


def test_idempotent(session, healthy_at_target):
    job = _make_job(session)
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    first_error = job.error
    upgrade_service._revive_false_restart_failures(session)
    session.refresh(job)
    assert job.status == "success"
    assert job.error == first_error  # 第二次不该反复叠加说明


def test_reconcile_jobs_includes_revive(session, healthy_at_target, monkeypatch):
    """reconcile_jobs 这个对外入口也要带上复核步骤。"""
    monkeypatch.setattr(upgrade_service, "_reconcile_restart_jobs", lambda db: None)
    monkeypatch.setattr(upgrade_service, "_reap_zombie_jobs", lambda db: None)
    job = _make_job(session)
    upgrade_service.reconcile_jobs(session)
    session.refresh(job)
    assert job.status == "success"
