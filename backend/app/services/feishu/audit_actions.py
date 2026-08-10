"""飞书卡片按钮触发的报工审核"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.feishu.oauth import get_user_by_feishu_open_id
from app.services.report_audit_actions import ReportAuditError, handle_audit_action


class FeishuAuditError(ReportAuditError):
    pass


def handle_card_action(db: Session, *, action: str, biz_type: str, biz_id: int, operator_open_id: str) -> str:
    auditor = get_user_by_feishu_open_id(db, operator_open_id)
    try:
        return handle_audit_action(
            db,
            action=action,
            biz_type=biz_type,
            biz_id=biz_id,
            auditor=auditor,
            channel_label="飞书",
        )
    except ReportAuditError as e:
        raise FeishuAuditError(str(e)) from e
