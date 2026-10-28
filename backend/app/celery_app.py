# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from kombu import Queue

from app.core.config import settings

logger = logging.getLogger(__name__)


celery = Celery("cenkormes")
celery.conf.update(
    broker_url=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_default_queue="celery",
    task_queues=[
        Queue("celery"),
    ],
)

celery.autodiscover_tasks(["app"])


@worker_process_init.connect
def _import_extension_modules_in_worker(**kwargs):
    """Worker 子进程启动时 import 已装扩展模块，使扩展的 @shared_task 注册到本进程。

    worker 只通过 ``celery -A app.celery_app`` 启动，不会 import app.main；
    不加这一步，扩展声明的 celery 任务（如 stock_safety.scan）在 worker 端
    永远是「未注册任务」，beat 投递后无人消费。
    """
    try:
        from app.extension_host import import_extension_modules

        result = import_extension_modules()
        failed = (result or {}).get("failed") or {}
        if failed:
            logger.warning("worker 导入扩展模块失败 %d 个: %s", len(failed), failed)
    except Exception:  # noqa: BLE001 - 扩展加载失败不应阻止 worker 启动
        logger.exception("worker 加载扩展任务模块失败")

celery.conf.beat_schedule = {
    "salary-daily-hourly-calc": {
        "task": "salary.daily_hourly_calc",
        "schedule": crontab(hour=1, minute=0),
    },
    "salary-monthly-summary": {
        "task": "salary.monthly_summary",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),
    },
}

# ── 默认定时任务定义（供 cron_job_seeder 与 /admin/cron-jobs/defaults 使用）──
DEFAULT_CRON_JOBS = [
    {
        "name": "salary-daily-hourly-calc",
        "task_name": "salary.daily_hourly_calc",
        "description": "计件/时薪每日计算",
        "cron_minute": "0",
        "cron_hour": "1",
        "cron_day_of_month": "*",
        "cron_month_of_year": "*",
        "cron_day_of_week": "*",
    },
    {
        "name": "salary-monthly-summary",
        "task_name": "salary.monthly_summary",
        "description": "薪资月度汇总",
        "cron_minute": "0",
        "cron_hour": "2",
        "cron_day_of_month": "1",
        "cron_month_of_year": "*",
        "cron_day_of_week": "*",
    },
    {
        "name": "production-automation-pipeline",
        "task_name": "production.automation.pipeline",
        "description": "生产自动化流水线扫描（已到开始日的计划自动排产/发布）",
        "cron_minute": "*/5",
        "cron_hour": "*",
        "cron_day_of_month": "*",
        "cron_month_of_year": "*",
        "cron_day_of_week": "*",
    },
]
