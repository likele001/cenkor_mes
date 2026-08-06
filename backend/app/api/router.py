from fastapi import APIRouter, Depends

from app.core.deps import get_current_user

from app.api.admin.master.router import router as admin_master_router
from app.api.admin.production.router import router as admin_production_router
from app.api.admin.system.router import router as admin_system_router
from app.api.admin.trace.router import router as admin_trace_router
from app.api.admin.equipment.router import router as admin_equipment_router
from app.api.admin.dictionary.router import router as admin_dictionary_router
from app.api.admin.production.plans import router as admin_plans_router
from app.api.h5.router import router as h5_router
from app.api.admin.reports.router import router as admin_reports_router
from app.api.dashboard.router import router as dashboard_router
from app.api.v1.auth import router as auth_router
from app.api.v1.captcha import router as captcha_router
from app.api.v1.files import router as files_router
from app.api.admin.shift.router import router as admin_shift_router
from app.api.admin.exec_dashboard.router import router as admin_exec_dashboard_router
from app.api.ws.dashboard import router as ws_dashboard_router
from app.api.admin.cron_jobs import router as admin_cron_jobs_router
from app.api.admin.export_jobs import router as admin_export_jobs_router
from app.api.admin.automation.router import router as admin_automation_router
from app.api.admin.ai.router import router as admin_ai_router
from app.api.admin.finance.router import router as admin_finance_router
from app.api.admin.purchase.router import router as admin_purchase_router
from app.api.admin.warehouse.router import router as admin_warehouse_router
from app.api.admin.approval.router import router as admin_approval_router
from app.api.admin.mrp.router import router as admin_mrp_router
from app.api.admin.subcontract.router import router as admin_subcontract_router


api_router = APIRouter()
_admin_deps = [Depends(get_current_user)]
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(captcha_router, prefix="/auth/captcha", tags=["auth-captcha"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"], dependencies=_admin_deps)
api_router.include_router(admin_master_router, prefix="/admin/master", tags=["admin-master"], dependencies=_admin_deps)
api_router.include_router(admin_production_router, prefix="/admin/production", tags=["admin-production"], dependencies=_admin_deps)
api_router.include_router(admin_system_router, prefix="/admin/system", tags=["admin-system"], dependencies=_admin_deps)
api_router.include_router(admin_trace_router, prefix="/admin/trace", tags=["admin-trace"], dependencies=_admin_deps)
api_router.include_router(admin_equipment_router, prefix="/admin/equipment", tags=["admin-equipment"], dependencies=_admin_deps)
api_router.include_router(admin_dictionary_router, prefix="/admin/dictionary", tags=["admin-dictionary"], dependencies=_admin_deps)
api_router.include_router(admin_reports_router, prefix="/admin/reports", tags=["admin-reports"], dependencies=_admin_deps)
api_router.include_router(admin_plans_router, prefix="/admin", tags=["admin-plans"], dependencies=_admin_deps)
api_router.include_router(admin_shift_router, prefix="/admin/shift", tags=["admin-shift"], dependencies=_admin_deps)
api_router.include_router(admin_exec_dashboard_router, prefix="/admin/exec-dashboard", tags=["admin-exec-dashboard"], dependencies=_admin_deps)
api_router.include_router(admin_cron_jobs_router, prefix="/admin/cron-jobs", tags=["admin-cron-jobs"], dependencies=_admin_deps)
api_router.include_router(admin_export_jobs_router, prefix="/admin", tags=["admin-export-jobs"], dependencies=_admin_deps)
api_router.include_router(admin_ai_router, prefix="/ai", tags=["ai"], dependencies=_admin_deps)
api_router.include_router(admin_automation_router, prefix="/admin/automation", tags=["admin-automation"], dependencies=_admin_deps)
api_router.include_router(admin_finance_router, prefix="/admin/finance", tags=["admin-finance"], dependencies=_admin_deps)
api_router.include_router(admin_purchase_router, prefix="/admin/purchase", tags=["admin-purchase"], dependencies=_admin_deps)
api_router.include_router(admin_warehouse_router, prefix="/admin/warehouse", tags=["admin-warehouse"], dependencies=_admin_deps)
api_router.include_router(admin_approval_router, prefix="/admin/approval", tags=["admin-approval"], dependencies=_admin_deps)
api_router.include_router(admin_mrp_router, prefix="/admin/mrp", tags=["admin-mrp"], dependencies=_admin_deps)
api_router.include_router(admin_subcontract_router, prefix="/admin/subcontract", tags=["admin-subcontract"], dependencies=_admin_deps)
api_router.include_router(h5_router, prefix="/h5", tags=["h5"])
api_router.include_router(ws_dashboard_router, prefix="/ws", tags=["websocket"])

from app.api.miniapp.auth import router as miniapp_auth_router

api_router.include_router(miniapp_auth_router, prefix="/miniapp/auth", tags=["miniapp"])
