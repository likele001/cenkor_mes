import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.export_job import ExportJob


def create_export_job(
    db: Session,
    *,
    job_type: str,
    created_by: int | None,
    params: dict | None,
) -> ExportJob:
    obj = ExportJob(
        job_type=job_type,
        status="pending",
        created_by=created_by,
        params_json=json.dumps(params or {}, ensure_ascii=False),
    )
    db.add(obj)
    db.flush()
    return obj


def get_export_job_by_id(db: Session, *, job_id: int) -> ExportJob | None:
    return db.scalar(select(ExportJob).where(ExportJob.id == job_id))


def list_export_jobs(
    db: Session,
    *,
    job_type: str | None = None,
    status: str | None = None,
    created_by: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ExportJob]:
    stmt = select(ExportJob)
    if job_type:
        stmt = stmt.where(ExportJob.job_type == job_type)
    if status:
        stmt = stmt.where(ExportJob.status == status)
    if created_by:
        stmt = stmt.where(ExportJob.created_by == created_by)
    stmt = stmt.order_by(ExportJob.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()
