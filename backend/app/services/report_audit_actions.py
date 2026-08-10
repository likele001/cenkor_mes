"""报工审核动作（通道无关，飞书/钉钉等共用）"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.notification import create_notification
from app.crud.report import create_audit, get_report_by_id, update_report_status
from app.crud.report_unit import create_unit_audit, get_unit_by_id, reset_unit_to_draft
from app.models.user import User


class ReportAuditError(Exception):
    pass


def _ensure_auditor(db: Session, auditor: User | None) -> User:
    if not auditor or not auditor.is_active:
        raise ReportAuditError("IM 账号未绑定系统用户")
    return auditor


def _has_report_audit(db: Session, user: User) -> bool:
    if user.is_superuser:
        return True
    from app.services.wecom.targets import _users_with_permission

    return user.id in _users_with_permission(db, "report.audit")


def leader_approve_report(
    db: Session,
    *,
    report_id: int,
    auditor: User,
    channel_label: str = "IM",
) -> str:
    auditor = _ensure_auditor(db, auditor)
    if not _has_report_audit(db, auditor):
        raise ReportAuditError("无报工审核权限")
    report = get_report_by_id(db, report_id)
    if not report:
        raise ReportAuditError("报工记录不存在")
    if report.status != "submitted":
        raise ReportAuditError(f"当前状态不可初审：{report.status}")
    create_audit(
        db,
        report.id,
        auditor.id,
        "leader",
        "approve",
        f"{channel_label}卡片初审",
    )
    update_report_status(db, report, "leader_approved")
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工已初审通过",
        content=f"报工 {report.id} 已由 {auditor.full_name or auditor.username} 初审通过（{channel_label}）",
        level="info",
        biz_type="report",
        biz_id=report.id,
        feishu_event="report.leader_approved",
    )
    return f"报工 #{report.id} 已初审通过"


def reject_report(
    db: Session,
    *,
    report_id: int,
    auditor: User,
    reason: str | None = None,
    channel_label: str = "IM",
) -> str:
    reason = reason or f"{channel_label}卡片驳回"
    auditor = _ensure_auditor(db, auditor)
    if not _has_report_audit(db, auditor):
        raise ReportAuditError("无报工审核权限")
    report = get_report_by_id(db, report_id)
    if not report:
        raise ReportAuditError("报工记录不存在")
    if report.status not in ("submitted", "leader_approved"):
        raise ReportAuditError(f"当前状态不可驳回：{report.status}")
    create_audit(
        db,
        report.id,
        auditor.id,
        "qc",
        "reject",
        reason,
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
        feishu_event="report.rejected",
    )
    return f"报工 #{report.id} 已驳回"


def leader_approve_unit(
    db: Session,
    *,
    unit_id: int,
    auditor: User,
    channel_label: str = "IM",
) -> str:
    auditor = _ensure_auditor(db, auditor)
    if not _has_report_audit(db, auditor):
        raise ReportAuditError("无报工审核权限")
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise ReportAuditError("报工件次不存在")
    if unit.status not in ("submitted", "leader_approved") and not unit.status.startswith("step_"):
        raise ReportAuditError(f"当前状态不可审核：{unit.status}")
    from app.services.approval_flow_resolver import get_status_after_approval

    audit_count = len([a for a in unit.audits if a.action == "approve"])
    new_status = get_status_after_approval(db, audit_count)
    create_unit_audit(
        db,
        report_unit_id=unit.id,
        auditor_id=auditor.id,
        audit_level="leader" if audit_count == 0 else "qc",
        action="approve",
        reason=f"{channel_label}卡片审核",
    )
    unit.status = new_status
    create_notification(
        db,
        user_id=unit.user_id,
        title="件次报工已审核通过",
        content=f"任务件次 #{unit.unit_seq} 已审核通过（{channel_label}）",
        level="info",
        biz_type="report_unit",
        biz_id=unit.id,
        feishu_event="report.leader_approved",
    )
    return f"件次 #{unit.unit_seq} 已审核通过"


def reject_unit(
    db: Session,
    *,
    unit_id: int,
    auditor: User,
    reason: str | None = None,
    channel_label: str = "IM",
) -> str:
    reason = reason or f"{channel_label}卡片驳回"
    auditor = _ensure_auditor(db, auditor)
    if not _has_report_audit(db, auditor):
        raise ReportAuditError("无报工审核权限")
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise ReportAuditError("报工件次不存在")
    if unit.status not in ("submitted", "leader_approved") and not unit.status.startswith("step_"):
        raise ReportAuditError(f"当前状态不可驳回：{unit.status}")
    create_unit_audit(
        db,
        report_unit_id=unit.id,
        auditor_id=auditor.id,
        audit_level="qc",
        action="reject",
        reason=reason,
    )
    reset_unit_to_draft(db, unit)
    create_notification(
        db,
        user_id=unit.user_id,
        title="件次报工被驳回",
        content=f"第{unit.unit_seq}件被驳回：{reason}",
        level="warning",
        biz_type="report_unit",
        biz_id=unit.id,
        feishu_event="report.rejected",
    )
    return f"件次 #{unit.unit_seq} 已驳回"


def handle_audit_action(
    db: Session,
    *,
    action: str,
    biz_type: str,
    biz_id: int,
    auditor: User,
    channel_label: str = "IM",
) -> str:
    if action == "report_leader_approve" and biz_type == "report":
        return leader_approve_report(db, report_id=biz_id, auditor=auditor, channel_label=channel_label)
    if action == "report_reject" and biz_type == "report":
        return reject_report(db, report_id=biz_id, auditor=auditor, channel_label=channel_label)
    if action == "unit_leader_approve" and biz_type == "report_unit":
        return leader_approve_unit(db, unit_id=biz_id, auditor=auditor, channel_label=channel_label)
    if action == "unit_reject" and biz_type == "report_unit":
        return reject_unit(db, unit_id=biz_id, auditor=auditor, channel_label=channel_label)
    raise ReportAuditError(f"不支持的操作：{action}")
