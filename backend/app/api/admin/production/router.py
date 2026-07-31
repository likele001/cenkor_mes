from fastapi import APIRouter

from app.api.admin.production.customers import router as customers_router
from app.api.admin.production.orders import router as orders_router
from app.api.admin.production.reports import router as reports_router
from app.api.admin.production.report_units import router as report_units_router
from app.api.admin.production.salary_reports import router as salary_reports_router
from app.api.admin.production.quality import router as quality_router
from app.api.admin.production.assignments import router as assignments_router
from app.api.admin.production.tasks import router as tasks_router
from app.api.admin.production.work_orders import router as work_orders_router
from app.api.admin.production.crm import router as crm_router


router = APIRouter()
router.include_router(customers_router, prefix="/customers", tags=["admin-production-customers"])
router.include_router(orders_router, prefix="/orders", tags=["admin-production-orders"])
router.include_router(work_orders_router, prefix="/work-orders", tags=["admin-production-work-orders"])
router.include_router(tasks_router, prefix="/tasks", tags=["admin-production-tasks"])
router.include_router(assignments_router, prefix="/assignments", tags=["admin-production-assignments"])
router.include_router(reports_router, prefix="/reports", tags=["admin-production-reports"])
router.include_router(report_units_router, tags=["admin-production-report-units"])
router.include_router(salary_reports_router, prefix="/reports", tags=["admin-production-reports"])
router.include_router(quality_router, prefix="", tags=["admin-production-quality"])
router.include_router(crm_router, prefix="/crm", tags=["admin-production-crm"])
