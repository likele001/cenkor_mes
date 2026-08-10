"""企业微信卡片按钮触发的报工审核"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.notification import create_notification
from app.crud.report import create_audit, get_report_by_id, update_report_status
from app.crud.report_unit import create_unit_audit, get_unit_by_id, reset_unit_to_draft
from app.models.user import User


class WecomAuditError(Exception):
    pass


def _ensure_auditor(db: Session, tenant_id: int, auditor: User | None) -> User:
    if not auditor or auditor.tenant_id != tenant_id or not auditor.is_active:
        raise WecomAuditError("企业微信账号未绑定系统用户")
    return auditor


def _has_report_audit(db: Session, tenant_id: int, user: User) -> bool:
    if user.is_superuser:
        return True
    from app.services.wecom.targets import _users_with_permission
    return user.id in _users_with_permission(db, "report.audit")


def leader_approve_report(db: Session, *, tenant_id: int, report_id: int, auditor: User) -> str:
    auditor = _ensure_auditor(db, tenant_id, auditor)
    if not _has_report_audit(db, tenant_id, auditor):
        raise WecomAuditError("无报工审核权限")
    report = get_report_by_id(db, report_id=report_id)
    if not report:
        raise WecomAuditError("报工记录不存在")
    if report.status != "submitted":
        raise WecomAuditError(f"当前状态不可初审：{report.status}")
    create_audit(
        db,
        report_id=report.id,
        auditor_id=auditor.id,
        audit_level="leader",
        action="approve",
        reason="企业微信初审",
    )
    update_report_status(db, report, "leader_approved")
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工已初审通过",
        content=f"报工 {report.id} 已由 {auditor.full_name or auditor.username} 初审通过（企业微信）",
        level="info",
        biz_type="report",
        biz_id=report.id,
    )
    return f"报工 #{report.id} 已初审通过"


def reject_report(db: Session, *, tenant_id: int, report_id: int, auditor: User, reason: str = "企业微信驳回") -> str:
    auditor = _ensure_auditor(db, tenant_id, auditor)
    if not _has_report_audit(db, tenant_id, auditor):
        raise WecomAuditError("无报工审核权限")
    report = get_report_by_id(db, report_id=report_id)
    if not report:
        raise WecomAuditError("报工记录不存在")
    if report.status not in ("submitted", "leader_approved"):
        raise WecomAuditError(f"当前状态不可驳回：{report.status}")
    create_audit(
        db,
        report_id=report.id,
        auditor_id=auditor.id,
        audit_level="qc",
        action="reject",
        reason=reason,
    )
    update_report_status(db, report, "rejected")
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工被驳回",
        content=f"报工 {report.id} 被驳回：{reason}",
        level="warning",
        biz_type="report",
        biz_id=report.id,
    )
    return f"报工 #{report.id} 已驳回"


def handle_card_action(db: Session, *, action: str, biz_type: str, biz_id: int, tenant_id: int, operator_userid: str) -> str:
    from app.services.wecom.oauth import get_user_by_wecom_userid

    auditor = get_user_by_wecom_userid(db, tenant_id, operator_userid)
    if action == "report_leader_approve" and biz_type == "report":
        return leader_approve_report(db, tenant_id=tenant_id, report_id=biz_id, auditor=auditor)
    if action == "report_reject" and biz_type == "report":
        return reject_report(db, tenant_id=tenant_id, report_id=biz_id, auditor=auditor)
    raise WecomAuditError(f"不支持的操作：{action}")
