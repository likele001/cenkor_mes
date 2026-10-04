# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from sqlalchemy.orm import Session

from app.models.tenant import Tenant

DEFAULT_TENANT_ID = 1


def ensure_default_tenant(db: Session) -> bool:
    """ERP/CRM 有 17 张表的外键指向 tenants.id，而单租户版 tenant_id 恒为 1，
    tenants 为空会让客户首次写凭证/资产/线索时直接 FK 失败。"""
    if db.get(Tenant, DEFAULT_TENANT_ID):
        return False
    db.add(Tenant(
        id=DEFAULT_TENANT_ID,
        code="default",
        name="默认企业",
        status="active",
    ))
    db.flush()
    return True
