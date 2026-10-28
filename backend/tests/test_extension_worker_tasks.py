# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""Worker/Beat 进程加载扩展任务模块 + DatabaseScheduler 合并 conf.beat_schedule。

覆盖 issue 3 的根因修复：worker/beat 不再只靠 web 进程的 mount_all 加载扩展，
扩展的 @shared_task 与 conf.beat_schedule 自注册项在 worker 启动与 beat 重载时
都会生效（stock_safety.scan 等扩展任务可被投递、被消费、被调度）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from celery.schedules import crontab
from sqlalchemy import create_engine

from app.core.config import settings
from app.extension_host.loader import extension_module_name, purge_extension_modules

TASK_NAME = "faketask.scan"
BEAT_ENTRY = "ext.faketask.scan"


def _manifest(key: str) -> str:
    return json.dumps(
        {
            "key": key,
            "name": f"{key} 应用",
            "version": "1.0.0",
            "manifest_version": 2,
            "schema_version": 1,
            "product": "cenkormes",
            "min_core_version": "2.0.0",
            "permissions": [{"code": f"ext.{key}.view", "name": "查看"}],
            "menus": [{"title": "页面", "path": f"/ext/{key}"}],
            "data": {"retention": "keep", "tables": []},
        },
        ensure_ascii=False,
    )


def _write_fake_extension(base: Path, key: str, *, with_router: bool = True) -> Path:
    ext = base / key
    ext.mkdir()
    (ext / "manifest.json").write_text(_manifest(key), encoding="utf-8")
    if with_router:
        (ext / "router.py").write_text(
            "from fastapi import APIRouter\n"
            "from celery import shared_task\n"
            "from celery.schedules import crontab\n\n"
            "router = APIRouter()\n\n\n"
            f"@shared_task(name='{TASK_NAME}')\n"
            "def scan():\n"
            "    return {'ok': True}\n\n\n"
            "def _register_on_load():\n"
            "    from app.celery_app import celery\n"
            "    schedule = getattr(celery.conf, 'beat_schedule', None) or {}\n"
            "    schedule.setdefault(\n"
            f"        '{BEAT_ENTRY}',\n"
            f"        {{'task': '{TASK_NAME}', 'schedule': crontab(minute='*/5')}},\n"
            "    )\n\n\n"
            "_register_on_load()\n",
            encoding="utf-8",
        )
    return ext


def test_import_extension_modules_loads_tasks_and_beat(tmp_path, monkeypatch):
    """fake 扩展被 import：模块进 sys.modules、任务注册、beat 条目进 conf。"""
    from app.celery_app import celery
    from app.extension_host.host import import_extension_modules

    key = "faketask"
    base = tmp_path / "exts"
    base.mkdir()
    _write_fake_extension(base, key)
    _write_fake_extension(base, "dataonly", with_router=False)  # 无 router 的纯数据扩展

    monkeypatch.setattr(settings, "EXTENSIONS_DIR", str(base))
    monkeypatch.setattr(settings, "EXTENSIONS_ENABLED", True)

    conf_before = dict(getattr(celery.conf, "beat_schedule", None) or {})
    try:
        result = import_extension_modules()
        assert result["ok"] is True
        assert result["loaded"] == [key]
        assert result["failed"] == {}

        # 以包名注册进 sys.modules（扩展内 from . import x 可用）
        assert extension_module_name(key) in sys.modules
        mod = sys.modules[extension_module_name(key)]
        assert getattr(mod, "router", None) is not None

        # beat 条目已自注册进 conf.beat_schedule
        schedule = celery.conf.beat_schedule
        assert BEAT_ENTRY in schedule
        assert schedule[BEAT_ENTRY]["task"] == TASK_NAME

        # @shared_task：app 未 finalize 时挂 connect_on_app_finalize，finalize 后进注册表
        celery.finalize()
        assert TASK_NAME in celery.tasks
    finally:
        schedule = getattr(celery.conf, "beat_schedule", None)
        if schedule is not None:
            schedule.clear()
            schedule.update(conf_before)
        celery.tasks.pop(TASK_NAME, None)
        purge_extension_modules(key)


def test_import_extension_modules_disabled(monkeypatch):
    """扩展总开关关闭时直接跳过，不扫描目录。"""
    monkeypatch.setattr(settings, "EXTENSIONS_ENABLED", False)
    from app.extension_host.host import import_extension_modules

    result = import_extension_modules()
    assert result == {"ok": True, "loaded": [], "failed": {}, "reason": "disabled"}


def test_database_scheduler_merges_conf_beat_schedule(tmp_path, monkeypatch):
    """Beat 调度表 = cron_jobs(DB) + conf.beat_schedule(扩展自注册)，DB 同名优先。"""
    from app.celery_app import celery
    from app.models.cron_job import CronJob
    from app.schedulers.database import DatabaseScheduler

    db_path = tmp_path / "beat.db"
    monkeypatch.setattr(settings, "DB_URL", f"sqlite:///{db_path}")

    engine = create_engine(f"sqlite:///{db_path}")
    CronJob.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(
            CronJob.__table__.insert().values(
                name="salary-daily-hourly-calc",
                task_name="salary.daily_hourly_calc",
                description="db 版本",
                enabled=True,
                is_system=False,
                cron_minute="0", cron_hour="1",
                cron_day_of_month="*", cron_month_of_year="*", cron_day_of_week="*",
            )
        )
        # 与 conf 同名条目：DB 优先，不被 conf 覆盖
        conn.execute(
            CronJob.__table__.insert().values(
                name=BEAT_ENTRY,
                task_name="db.winner.task",
                description="同名词条",
                enabled=True,
                is_system=False,
                cron_minute="*/10", cron_hour="*",
                cron_day_of_month="*", cron_month_of_year="*", cron_day_of_week="*",
            )
        )

    # 测试内不扫描真实扩展目录：把 import_extension_modules 换成记录调用的 no-op
    import app.extension_host as ext_host

    calls: list[int] = []
    monkeypatch.setattr(
        ext_host, "import_extension_modules",
        lambda: calls.append(1) or {"ok": True, "loaded": [], "failed": {}},
    )

    conf_before = dict(celery.conf.beat_schedule or {})
    celery.conf.beat_schedule[BEAT_ENTRY] = {
        "task": "conf.loser.task",
        "schedule": crontab(minute="*/5"),
    }
    try:
        sched = DatabaseScheduler(celery)
        try:
            assert calls == [1], "setup_schedule 应导入一次扩展模块"

            merged = sched._schedule_dict
            # DB 条目
            assert merged[BEAT_ENTRY]["task"] == "db.winner.task"
            assert 10 in merged[BEAT_ENTRY]["schedule"].minute
            assert merged["salary-daily-hourly-calc"]["task"] == "salary.daily_hourly_calc"
            # conf 中无 DB 对应的条目被合入
            assert merged["salary-monthly-summary"]["task"] == "salary.monthly_summary"
            # 父类 schedule（ScheduleEntry 视图）同步可见
            assert BEAT_ENTRY in sched.schedule
            assert sched.schedule[BEAT_ENTRY].task == "db.winner.task"

            # 重载（Redis reload 信号路径）幂等且再次导入扩展模块
            sched._reload_schedule()
            assert calls == [1, 1]
            assert sched._schedule_dict[BEAT_ENTRY]["task"] == "db.winner.task"
        finally:
            sched.close()
    finally:
        celery.conf.beat_schedule.clear()
        celery.conf.beat_schedule.update(conf_before)
