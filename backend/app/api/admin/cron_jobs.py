"""
定时任务管理 API
- GET /admin/cron-jobs — 列表
- PUT /admin/cron-jobs/{id} — 更新（修改后发 Redis reload 信号）
- POST /admin/cron-jobs/reload — 手动触发重载
- GET /admin/cron-jobs/defaults — 获取系统默认任务定义
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import redis as redis_lib

from app.core.config import settings
from app.core.deps import get_db
from app.core.response import ok
from app.models.cron_job import CronJob

router = APIRouter()

RELOAD_KEY = "celery:beat:reload"


class CronJobUpdateIn(BaseModel):
    enabled: bool | None = None
    cron_minute: str | None = Field(None, max_length=10)
    cron_hour: str | None = Field(None, max_length=10)
    cron_day_of_month: str | None = Field(None, max_length=10)
    cron_month_of_year: str | None = Field(None, max_length=10)
    cron_day_of_week: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=255)


@router.get("")
def list_cron_jobs(db: Session = Depends(get_db)):
    """获取所有定时任务"""
    stmt = select(CronJob).order_by(CronJob.id)
    jobs = db.execute(stmt).scalars().all()
    return ok({"items": [j.to_dict() for j in jobs]})


@router.put("/{job_id}")
def update_cron_job(job_id: int, data: CronJobUpdateIn, db: Session = Depends(get_db)):
    """更新定时任务配置，修改后通知 Beat 重载"""
    job = db.get(CronJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(job, k, v)

    db.commit()
    db.refresh(job)

    # 通知 Beat 重新加载
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(RELOAD_KEY, "1", ex=60)
        r.close()
    except Exception:
        pass

    return ok(job.to_dict(), msg="保存成功，调度器将在 10 秒内生效")


@router.post("/reload")
def reload_cron_jobs():
    """手动触发 Beat 重新加载调度配置（10秒内生效）"""
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(RELOAD_KEY, "1", ex=60)
        r.close()
        return ok(None, msg="重载信号已发送，调度器将在 10 秒内重新加载")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/defaults")
def get_default_cron_jobs():
    """返回系统默认任务定义（用于前端参考）"""
    from app.celery_app import DEFAULT_CRON_JOBS
    return ok(DEFAULT_CRON_JOBS)
