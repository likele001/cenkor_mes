from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models.user import User
from app.services.report_media_settings import get_report_media_settings
from app.services.report_mode_settings import get_report_mode_settings

router = APIRouter()


@router.get("/settings/report-media")
def report_media_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_report_media_settings(db))


@router.get("/settings/report-mode")
def report_mode_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_report_mode_settings(db))
