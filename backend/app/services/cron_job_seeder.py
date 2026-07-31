"""定时任务默认配置迁移（幂等）"""
from sqlalchemy.orm import Session

from app.models.cron_job import CronJob
from app.celery_app import DEFAULT_CRON_JOBS


def seed_default_cron_jobs(db: Session) -> int:
    """将硬编码默认任务同步到 cron_jobs 表，返回新增数量"""
    added = 0
    for default in DEFAULT_CRON_JOBS:
        existing = db.query(CronJob).filter(CronJob.name == default["name"]).first()
        if existing:
            continue
        db.add(
            CronJob(
                name=default["name"],
                task_name=default["task_name"],
                description=default["description"],
                enabled=True,
                is_system=True,
                cron_minute=default["cron_minute"],
                cron_hour=default["cron_hour"],
                cron_day_of_month=default["cron_day_of_month"],
                cron_month_of_year=default["cron_month_of_year"],
                cron_day_of_week=default["cron_day_of_week"],
            )
        )
        added += 1
    if added:
        db.commit()
    return added
