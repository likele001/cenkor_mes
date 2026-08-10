"""钉钉卡片审核动作"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.dingtalk.oauth import get_user_by_dingtalk_userid
from app.services.report_audit_actions import ReportAuditError, handle_audit_action


class DingtalkAuditError(ReportAuditError):
    pass


def handle_card_action_token(db: Session, *, token: str) -> str:
    from app.services.dingtalk.card_action_tokens import parse_card_action_token

    data = parse_card_action_token(token)
    auditor = get_user_by_dingtalk_userid(db, data["dingtalk_userid"])
    try:
        return handle_audit_action(
            db,
            action=data["action"],
            biz_type=data["biz_type"],
            biz_id=data["biz_id"],
            auditor=auditor,
            channel_label="钉钉",
        )
    except ReportAuditError as e:
        raise DingtalkAuditError(str(e)) from e
