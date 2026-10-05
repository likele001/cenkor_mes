# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""仓库下拉选项：只要登录就能读，出入库页面都要用到它，不必人人开 warehouse.manage。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.warehouse import list_warehouses
from app.models.user import User

router = APIRouter()


@router.get("")
def warehouse_options_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok({
        "items": [
            {"id": w.id, "code": w.code, "name": w.name}
            for w in list_warehouses(db)
        ]
    })
