# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends

from app.core.deps import require_permissions
from app.api.admin.erp.invoices import router as invoices_router
from app.api.admin.erp.accounts import router as accounts_router
from app.api.admin.erp.vouchers import router as vouchers_router
from app.api.admin.erp.reports import router as reports_router
from app.api.admin.erp.costs import router as costs_router
from app.api.admin.erp.assets import router as assets_router


router = APIRouter(dependencies=[Depends(require_permissions(["erp.manage"]))])
router.include_router(invoices_router, prefix="/invoices", tags=["admin-erp-invoices"])
router.include_router(accounts_router, prefix="/accounts", tags=["admin-erp-accounts"])
router.include_router(vouchers_router, prefix="/vouchers", tags=["admin-erp-vouchers"])
router.include_router(reports_router, prefix="/reports", tags=["admin-erp-reports"])
router.include_router(costs_router, prefix="/costs", tags=["admin-erp-costs"])
router.include_router(assets_router, prefix="/assets", tags=["admin-erp-assets"])
