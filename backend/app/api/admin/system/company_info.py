# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.user import User
from app.services.company_settings import get_company_info, save_company_info

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])


class CompanyInfoIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=256)
    logo_attachment_id: int | None = Field(default=None, ge=1)
    clear_logo: bool = False


@router.get("/company-info")
def get_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_company_info(db))


@router.put("/company-info")
def put_api(
    payload: CompanyInfoIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        data = save_company_info(
            db,
            name=payload.name,
            phone=payload.phone,
            address=payload.address,
            logo_attachment_id=payload.logo_attachment_id,
            clear_logo=payload.clear_logo,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(data)
