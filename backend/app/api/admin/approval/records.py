# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""审批/状态变更留痕查询（只读）"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_permissions, get_current_user, get_db
from app.core.response import ok
from app.crud.approval_record import list_records
from app.models.approval_record import ApprovalRecord
from app.models.user import User

router = APIRouter()

BIZ_TYPES = (
    "order",
    "purchase_order",
    "warehouse_entry",
    "statement",
    "supplier_statement",
    "salary_slip",
    "mrp_plan",
)

# 留痕里常带金额与驳回原因，按业务类型映射到对应模块的查看/管理权限
BIZ_TYPE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "order": ("order.view", "order.manage"),
    "purchase_order": ("purchase.manage",),
    "warehouse_entry": ("warehouse.view", "warehouse.manage"),
    "statement": ("finance.manage",),
    "supplier_statement": ("finance.manage",),
    "salary_slip": ("salary.view", "salary.manage"),
    "mrp_plan": ("plan.manage", "production.plan"),
}


def _out(r: ApprovalRecord) -> dict:
    detail = None
    if r.detail:
        try:
            detail = json.loads(r.detail)
        except (TypeError, ValueError):
            detail = {"raw": r.detail}
    return {
        "id": r.id,
        "biz_type": r.biz_type,
        "biz_id": r.biz_id,
        "biz_code": r.biz_code,
        "action": r.action,
        "from_status": r.from_status,
        "to_status": r.to_status,
        "operator_id": r.operator_id,
        "operator_name": r.operator_name,
        "channel": r.channel,
        "reason": r.reason,
        "detail": detail,
        "created_at": r.created_at,
    }


@router.get("")
def list_records_api(
    biz_type: str | None = Query(default=None, max_length=32),
    biz_id: int | None = Query(default=None, ge=1),
    operator_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    if biz_type and biz_type not in BIZ_TYPES:
        raise HTTPException(status_code=400, detail="biz_type 不在允许范围内")
    if (biz_type is None) != (biz_id is None):
        raise HTTPException(status_code=400, detail="按单据查留痕需要同时提供 biz_type 与 biz_id")

    codes = set(permission_codes)
    allowed = [
        t for t in BIZ_TYPES
        if any(code in codes for code in BIZ_TYPE_PERMISSIONS[t])
    ]
    if getattr(user, "is_superuser", False):
        allowed = list(BIZ_TYPES)

    if biz_type is not None:
        if biz_type not in allowed:
            raise HTTPException(status_code=403, detail="无权查看该业务的审批留痕")
        items, total = list_records(
            db, biz_type=biz_type, biz_id=biz_id, operator_id=operator_id,
            action=action, offset=offset, limit=limit,
        )
    else:
        if not allowed:
            raise HTTPException(status_code=403, detail="无权查看审批留痕")
        items, total = list_records(
            db, biz_types=allowed, operator_id=operator_id,
            action=action, offset=offset, limit=limit,
        )
    return ok({"items": [_out(r) for r in items], "total": total})
