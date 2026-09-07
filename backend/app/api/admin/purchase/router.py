# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter

from app.api.admin.purchase.orders import router as orders_router


router = APIRouter()
router.include_router(orders_router, prefix="/orders", tags=["admin-purchase-orders"])
