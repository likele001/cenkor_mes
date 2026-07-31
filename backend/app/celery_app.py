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
        "task": "task_calculate_salary",
        "schedule": crontab(hour=1, minute=0),
    },
    "salary-monthly-summary": {
        "task": "task_generate_salary_slips",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),
    },
}
