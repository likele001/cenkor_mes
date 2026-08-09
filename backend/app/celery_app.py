from celery import Celery
from kombu import Queue
from celery.schedules import crontab

from app.core.config import settings


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
        "description": "生产自动化流水线扫描",
        "cron_minute": "*/5",
        "cron_hour": "*",
        "cron_day_of_month": "*",
        "cron_month_of_year": "*",
        "cron_day_of_week": "*",
    },
]
