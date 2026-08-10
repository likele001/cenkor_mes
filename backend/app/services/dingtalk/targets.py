"""钉钉推送目标解析（复用企微逻辑）"""

from app.services.wecom.targets import (  # noqa: F401
    get_user_department_and_workshop,
    notify_in_app_for_targets,
    resolve_alert_targets,
    resolve_targets,
)
