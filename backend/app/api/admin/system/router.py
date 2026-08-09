from fastapi import APIRouter

from app.api.admin.system.attachments import router as attachments_router
from app.api.admin.system.attendance_records import router as attendance_records_router
from app.api.admin.system.departments import router as departments_router
from app.api.admin.system.notifications import router as notifications_router
from app.api.admin.system.operation_logs import router as operation_logs_router
from app.api.admin.system.permissions import router as permissions_router
from app.api.admin.system.print_templates import router as print_templates_router
from app.api.admin.system.skills import router as skills_router
from app.api.admin.system.roles import router as roles_router
from app.api.admin.system.settings import router as settings_router
from app.api.admin.system.report_media import router as report_media_router
from app.api.admin.system.report_mode import router as report_mode_router
from app.api.admin.system.wechat_miniapp import router as wechat_miniapp_router
from app.api.admin.system.feishu import router as feishu_router
from app.api.admin.system.wecom import router as wecom_router
from app.api.admin.system.dingtalk import router as dingtalk_router
from app.api.admin.system.message_center import router as message_center_router
from app.api.admin.system.wechat_mp import router as wechat_mp_router
from app.api.admin.system.users import router as users_router
from app.api.admin.system.invites import router as invites_router
from app.api.admin.system.codes import router as codes_router
from app.api.admin.system.version import router as version_router


router = APIRouter()
router.include_router(codes_router, prefix="/codes", tags=["admin-system-codes"])
router.include_router(permissions_router, prefix="/permissions", tags=["admin-system-permissions"])
router.include_router(roles_router, prefix="/roles", tags=["admin-system-roles"])
router.include_router(users_router, prefix="/users", tags=["admin-system-users"])
router.include_router(invites_router, prefix="/invites", tags=["admin-system-invites"])
router.include_router(departments_router, prefix="/departments", tags=["admin-system-departments"])
router.include_router(settings_router, prefix="/settings", tags=["admin-system-settings"])
router.include_router(report_media_router, tags=["admin-system-report-media"])
router.include_router(report_mode_router, tags=["admin-system-report-mode"])
router.include_router(wechat_miniapp_router, tags=["admin-system-wechat-miniapp"])
router.include_router(feishu_router, tags=["admin-system-feishu"])
router.include_router(wecom_router, tags=["admin-system-wecom"])
router.include_router(dingtalk_router, tags=["admin-system-dingtalk"])
router.include_router(wechat_mp_router, tags=["admin-system-wechat-mp"])
router.include_router(message_center_router, prefix="/message-center", tags=["admin-system-message-center"])
router.include_router(print_templates_router, prefix="/print-templates", tags=["admin-system-print-templates"])
router.include_router(notifications_router, prefix="/notifications", tags=["admin-system-notifications"])
router.include_router(attendance_records_router, prefix="/attendance-records", tags=["admin-system-attendance-records"])
router.include_router(skills_router, prefix="/skills", tags=["admin-system-skills"])
router.include_router(attachments_router, prefix="/attachments", tags=["admin-system-attachments"])
router.include_router(operation_logs_router, prefix="/operation-logs", tags=["admin-system-operation-logs"])
router.include_router(version_router, prefix="/version", tags=["admin-system-version"])
