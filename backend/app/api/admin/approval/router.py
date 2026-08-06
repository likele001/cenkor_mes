from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.approval import (
    create_flow,
    delete_flow,
    get_flow,
    list_flows,
    set_steps,
    update_flow,
)
from app.models.user import User

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


class FlowCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    biz_type: str = Field(min_length=1, max_length=32)
    is_active: bool = True


class FlowUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None


class StepIn(BaseModel):
    step_order: int | None = None
    approver_role: str = Field(min_length=1, max_length=32)
    is_required: bool = True
    can_skip: bool = False
    label: str | None = Field(default=None, max_length=64)


class StepsUpdateIn(BaseModel):
    steps: list[StepIn]


def _flow_out(f) -> dict:
    return {
        "id": f.id, "name": f.name,
        "biz_type": f.biz_type, "is_active": f.is_active,
        "steps": [
            {
                "id": s.id, "step_order": s.step_order,
                "approver_role": s.approver_role,
                "is_required": s.is_required, "can_skip": s.can_skip,
                "label": s.label,
            }
            for s in sorted(f.steps, key=lambda x: x.step_order)
        ],
        "created_at": f.created_at, "updated_at": f.updated_at,
    }


@router.get("")
def list_api(biz_type: str | None = Query(default=None),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = list_flows(db, biz_type=biz_type)
    return ok({"items": [_flow_out(f) for f in items]})


@router.post("")
def create_api(payload: FlowCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = create_flow(db, name=payload.name, biz_type=payload.biz_type, is_active=payload.is_active)
    db.commit()
    return ok({"id": f.id, "name": f.name})


@router.get("/{flow_id}")
def get_api(flow_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = get_flow(db, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="审批流不存在")
    return ok(_flow_out(f))


@router.put("/{flow_id}")
def update_api(flow_id: int, payload: FlowUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = get_flow(db, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="审批流不存在")
    update_flow(db, f, name=payload.name, is_active=payload.is_active)
    db.commit()
    db.refresh(f)
    return ok(_flow_out(f))


@router.delete("/{flow_id}")
def delete_api(flow_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = get_flow(db, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="审批流不存在")
    delete_flow(db, f)
    db.commit()
    return ok({"deleted": True})


@router.put("/{flow_id}/steps")
def update_steps_api(flow_id: int, payload: StepsUpdateIn,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = get_flow(db, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="审批流不存在")
    if not payload.steps:
        raise HTTPException(status_code=400, detail="至少需要一个审批步骤")
    items = set_steps(db, flow_id, [s.model_dump() for s in payload.steps])
    db.commit()
    return ok({"count": len(items)})