import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation_log import AutomationLog


def create_automation_log(
    db: Session,
    *,
    trigger: str,
    action: str,
    status: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
    message: str | None = None,
    detail: dict | list | None = None,
    created_by: int | None = None,
) -> AutomationLog:
    row = AutomationLog(
        trigger=trigger,
        action=action,
        biz_type=biz_type,
        biz_id=biz_id,
        status=status,
        message=(message or "")[:512] if message else None,
        detail_json=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def list_automation_logs(
    db: Session,
    *,
    trigger: str | None = None,
    status: str | None = None,
    biz_type: str | None = None,
    biz_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AutomationLog]:
    stmt = select(AutomationLog)
    if trigger:
        stmt = stmt.where(AutomationLog.trigger == trigger)
    if status:
        stmt = stmt.where(AutomationLog.status == status)
    if biz_type:
        stmt = stmt.where(AutomationLog.biz_type == biz_type)
    if biz_id is not None:
        stmt = stmt.where(AutomationLog.biz_id == biz_id)
    stmt = stmt.order_by(AutomationLog.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())
