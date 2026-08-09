from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.automation_log import list_automation_logs
from app.models.user import User
from app.schemas.automation import AutomationDryRunIn, AutomationSettingsIn
from app.services.production_automation import precheck_order_for_automation, precheck_plan_for_automation
from app.services.production_automation_settings import get_automation_settings, save_automation_settings


router = APIRouter()


def _log_out(row) -> dict:
    return {
        "id": row.id,
        "trigger": row.trigger,
        "action": row.action,
        "biz_type": row.biz_type,
        "biz_id": row.biz_id,
        "status": row.status,
        "message": row.message,
        "detail_json": row.detail_json,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


@router.get("/settings", dependencies=[Depends(require_permissions(["setting.manage"]))])
def get_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_automation_settings(db, user.tenant_id))


@router.put("/settings", dependencies=[Depends(require_permissions(["setting.manage"]))])
def save_settings_api(
    payload: AutomationSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = save_automation_settings(db, user.tenant_id, payload.model_dump(exclude_none=True))
    db.commit()
    return ok(data)


@router.get("/logs", dependencies=[Depends(require_permissions(["setting.manage"]))])
def list_logs_api(
    trigger: str | None = Query(default=None),
    status: str | None = Query(default=None),
    biz_type: str | None = Query(default=None),
    biz_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_automation_logs(
        db,
        trigger=trigger,
        status=status,
        biz_type=biz_type,
        biz_id=biz_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_log_out(x) for x in items]})


@router.post("/dry-run", dependencies=[Depends(require_permissions(["plan.manage"]))])
def dry_run_api(
    payload: AutomationDryRunIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.order_id:
        return ok(
            precheck_order_for_automation(
                db,
                user.tenant_id,
                payload.order_id,
                allow_shortage=payload.allow_shortage,
            )
        )
    if payload.plan_id:
        return ok(precheck_plan_for_automation(db, user.tenant_id, payload.plan_id))
    raise HTTPException(status_code=400, detail="请提供 order_id 或 plan_id")
