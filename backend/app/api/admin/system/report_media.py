from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.user import User
from app.services.report_media_settings import get_report_media_settings, save_report_media_settings

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


class ReportMediaSettingsIn(BaseModel):
    max_video_seconds: int = Field(ge=5, le=120, default=15)
    max_video_mb: int = Field(ge=1, le=50, default=8)
    max_video_count: int = Field(ge=1, le=10, default=3)
    max_photo_count: int = Field(ge=1, le=20, default=5)
    camera_only: bool = True


@router.get("/report-media")
def get_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_report_media_settings(db, user.tenant_id))


@router.put("/report-media")
def put_api(
    payload: ReportMediaSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = save_report_media_settings(db, tenant_id=user.tenant_id, payload=payload.model_dump())
    db.commit()
    return ok(data)
