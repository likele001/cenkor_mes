"""通用 Excel 导出工具函数 — 供各报表导出 Celery task 复用"""
import json
import logging
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.attachment import create_attachment
from app.models.export_job import ExportJob
from app.storage import get_active_storage

logger = logging.getLogger(__name__)

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def load_job(db: Session, job_id: int) -> ExportJob | None:
    """加载导出任务，若已 running/success 则返回 None 表示跳过"""
    job = db.scalar(select(ExportJob).where(ExportJob.id == job_id))
    if not job:
        return None
    if job.status in ("running", "success"):
        return None  # 已在运行或已完成
    return job


def start_job(db: Session, job: ExportJob) -> dict | None:
    """标记任务为 running，返回解析后的 params dict"""
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.error_msg = None
    db.commit()
    params: dict = {}
    if job.params_json:
        try:
            params = json.loads(job.params_json) or {}
        except Exception:
            params = {}
    return params


def save_excel_and_finish(db: Session, job: ExportJob, wb, filename: str) -> dict:
    """保存 Excel 到存储 + 创建附件 + 标记 success，返回结果 dict"""
    from openpyxl import Workbook  # wb 已经由调用方构造

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    storage = get_active_storage(db)
    stored = storage.save(
        filename=filename,
        content_type=EXCEL_CONTENT_TYPE,
        stream=bio,
        max_size=settings.FILE_MAX_UPLOAD_SIZE,
    )
    if not job.created_by:
        raise ValueError("created_by 不能为空")

    att = create_attachment(
        db,
        uploader_id=int(job.created_by),
        storage_driver=stored.driver,
        storage_key=stored.key,
        original_filename=filename,
        content_type=EXCEL_CONTENT_TYPE,
        size=int(stored.size),
        sha256=stored.sha256,
    )
    job.result_attachment_id = att.id
    job.status = "success"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "status": "success", "job_id": int(job.id), "attachment_id": int(att.id)}


def fail_job(db: Session, job_id: int, error: Exception) -> dict:
    """标记任务失败"""
    try:
        db.rollback()
    except Exception:
        pass
    try:
        job = db.scalar(select(ExportJob).where(ExportJob.id == job_id))
        if job:
            job.status = "failed"
            job.error_msg = str(error)[:500]
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return {"ok": False, "status": "failed", "job_id": int(job_id)}
