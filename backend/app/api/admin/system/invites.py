from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.tenant_invite import create_invite, list_invites
from app.schemas.platform import TenantInviteCreateIn


router = APIRouter(dependencies=[Depends(require_permissions(["user.manage"]))])


@router.get("")
def list_invites_api(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    items = list_invites(db)
    return ok(
        {
            "items": [
                {
                    "id": i.id,
                    "token": i.token,
                    "role_code": i.role_code,
                    "max_uses": i.max_uses,
                    "used_count": i.used_count,
                    "expires_at": i.expires_at,
                    "created_at": i.created_at,
                }
                for i in items
            ],
        }
    )


@router.post("")
def create_invite_api(
    payload: TenantInviteCreateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    expires_at = None
    if payload.expires_days:
        expires_at = datetime.now() + timedelta(days=payload.expires_days)
    inv = create_invite(
        db,
        role_code=payload.role_code,
        max_uses=payload.max_uses,
        expires_at=expires_at,
        created_by=user.id,
    )
    db.commit()
    return ok(
        {
            "id": inv.id,
            "token": inv.token,
        }
    )
