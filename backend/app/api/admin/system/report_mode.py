from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.user import User
from app.services.report_mode_settings import get_report_mode_settings, save_report_mode_settings

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


class ReportModeSettingsIn(BaseModel):
    default_mode: str = Field(default="batch", pattern="^(batch|unit|lot)$")


@router.get("/report-mode")
def get_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_report_mode_settings(db, user.tenant_id))


@router.put("/report-mode")
def put_api(
    payload: ReportModeSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.default_mode == "lot":
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="批次流转模式尚未开放，请先使用批量或逐件")
    data = save_report_mode_settings(db, tenant_id=user.tenant_id, default_mode=payload.default_mode)
    db.commit()
    return ok(data)
