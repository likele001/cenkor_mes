from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.export_job import get_export_job_by_id
from app.models.user import User


router = APIRouter()


@router.get("/export-jobs/{job_id}")
def get_export_job_api(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_export_job_by_id(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    params = {}
    if job.params_json:
        import json
        try:
            params = json.loads(job.params_json) or {}
        except Exception:
            params = {}
    return ok({
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "params": params,
        "result_attachment_id": job.result_attachment_id,
        "error_msg": job.error_msg,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    })
