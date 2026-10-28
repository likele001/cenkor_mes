# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""基于数据库的 Celery Beat 调度器

从 cron_jobs 表读取调度配置，支持通过 Redis 信号热重载。
启动命令：
  celery -A app.celery_app.celery beat -S app.schedulers.database:DatabaseScheduler
"""
import logging
import time
from typing import Dict

import redis as redis_lib
from celery.beat import Scheduler
from celery.schedules import crontab
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis 键：写入任意值触发重载 / 写入任意值触发优雅退出（systemd Restart=always 拉起）
RELOAD_KEY = "celery:beat:reload"
SHUTDOWN_KEY = "celery:beat:shutdown"
RELOAD_CHECK_INTERVAL = 10  # 秒


def check_control_signals(r) -> str | None:
    """检查并消费控制信号键，返回 'shutdown' / 'reload' / None。

    退出信号走 SystemExit（BaseException），不会被子类 except Exception 吞掉；
    beat 进程退出后由 systemd（Restart=always）拉起新进程加载最新代码。
    """
    if r.get(SHUTDOWN_KEY):
        r.delete(SHUTDOWN_KEY)
        return "shutdown"
    if r.get(RELOAD_KEY):
        r.delete(RELOAD_KEY)
        return "reload"
    return None


class DatabaseScheduler(Scheduler):
    """从 cron_jobs 表加载调度配置，每 10 秒检查 Redis 重载信号"""

    def __init__(self, app, **kwargs):
        self._engine = None
        self._last_sync: float = 0.0
        self._schedule_dict: Dict[str, dict] = {}
        super().__init__(app, **kwargs)

    def setup_schedule(self):
        """启动时：导入扩展模块（注册 @shared_task 与 conf.beat_schedule 自注册项），
        从数据库加载调度配置，并合并静态 beat_schedule（DB 同名条目优先）。"""
        db_url = settings.DB_URL
        self._engine = create_engine(
            db_url,
            pool_size=2,
            max_overflow=2,
            pool_pre_ping=True,
        )
        self._reload_schedule()

    def _reload_schedule(self) -> None:
        """重载完整调度：扩展模块 → cron_jobs 表 → 静态 beat_schedule。"""
        try:
            from app.extension_host import import_extension_modules

            import_extension_modules()
        except Exception:
            logger.exception("Failed to import extension modules")
        self._load_from_db()
        # 扩展在 import 期自注册 conf.beat_schedule 条目；DB 同名条目优先（不被覆盖）
        conf = getattr(self.app.conf, "beat_schedule", None) or {}
        added = 0
        for name, entry in conf.items():
            if name not in self._schedule_dict:
                self._schedule_dict[name] = dict(entry)
                added += 1
        if added:
            logger.info("DatabaseScheduler merged %d static beat_schedule entries", added)
        self.merge_inplace(self._schedule_dict)

    def _load_from_db(self) -> None:
        """从 cron_jobs 表读取所有启用的任务"""
        from app.models.cron_job import CronJob

        new_schedule: Dict[str, dict] = {}
        try:
            with Session(self._engine) as db:
                stmt = select(CronJob).where(CronJob.enabled == True)
                jobs = db.execute(stmt).scalars().all()
                for job in jobs:
                    new_schedule[job.name] = {
                        "task": job.task_name,
                        "schedule": crontab(
                            minute=job.cron_minute,
                            hour=job.cron_hour,
                            day_of_month=job.cron_day_of_month,
                            month_of_year=job.cron_month_of_year,
                            day_of_week=job.cron_day_of_week,
                        ),
                    }
                self._schedule_dict = new_schedule
                logger.info(
                    "DatabaseScheduler loaded %d enabled cron jobs", len(new_schedule),
                )
        except Exception:
            logger.exception("Failed to load cron jobs from database")

        # 安装到父类的 schedule dict
        self.merge_inplace(self._schedule_dict)

    def tick(self) -> float:
        """每次 tick 检查 Redis 控制信号（退出/重载）"""
        now = time.monotonic()
        if now - self._last_sync > RELOAD_CHECK_INTERVAL:
            self._last_sync = now
            try:
                r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
                try:
                    signal = check_control_signals(r)
                finally:
                    r.close()
                if signal == "shutdown":
                    logger.info("Shutdown signal received, exiting (systemd will restart)")
                    raise SystemExit(0)
                if signal == "reload":
                    logger.info("Reload signal received, re-loading schedule from DB")
                    self._reload_schedule()
            except SystemExit:
                raise
            except Exception:
                pass

        return super().tick()

    def close(self):
        """释放数据库引擎"""
        if self._engine:
            self._engine.dispose()
        super().close()
