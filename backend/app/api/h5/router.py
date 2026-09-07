# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter

from app.api.h5.tasks import router as h5_tasks_router
from app.api.h5.report_units import router as h5_report_units_router
from app.api.h5.attendance import router as h5_attendance_router
from app.api.h5.customer import router as h5_customer_router
from app.api.h5.notifications import router as h5_notifications_router
from app.api.h5.salary_slips import router as h5_salary_slips_router
from app.api.h5.settings_media import router as h5_settings_media_router
from app.api.h5.feishu import router as h5_feishu_router


router = APIRouter()
router.include_router(h5_feishu_router, tags=["h5-feishu"])
router.include_router(h5_settings_media_router)
router.include_router(h5_tasks_router)
router.include_router(h5_report_units_router)
router.include_router(h5_attendance_router)
router.include_router(h5_customer_router, prefix="/customer", tags=["h5-customer"])
router.include_router(h5_salary_slips_router)
router.include_router(h5_notifications_router)
from app.api.h5.public_trace import router as h5_public_trace_router

router.include_router(h5_public_trace_router, prefix="/public", tags=["h5-public"])
