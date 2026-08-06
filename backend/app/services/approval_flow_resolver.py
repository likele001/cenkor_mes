"""审批流解析器 — 支持动态配置与默认回退

根据 ApprovalFlow / ApprovalStep 数据库配置动态解析审批步骤，
若未配置则回退到默认的 2 级审批流（leader → qc）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import ApprovalFlow, ApprovalStep

# ── 默认审批流（数据库无配置时回退） ──
_DEFAULT_STEPS: list[dict] = [
    {"approver_role": "leader", "label": "班组长审批", "is_required": True, "can_skip": False},
    {"approver_role": "qc", "label": "质检审批", "is_required": True, "can_skip": False},
]

_DEFAULT_STATUS_MAP: dict[int, str] = {
    0: "leader_approved",
    1: "qc_approved",
}

_TERMINAL_STATUSES = {"qc_approved", "rejected"}


def _load_flow_steps(db: Session, biz_type: str = "report") -> list[dict]:
    """从数据库加载审批流步骤，若未配置则返回默认"""
    flow = db.scalar(
        select(ApprovalFlow).where(
            ApprovalFlow.biz_type == biz_type,
            ApprovalFlow.is_active.is_(True),
        )
    )
    if not flow:
        return _DEFAULT_STEPS

    steps = (
        db.execute(
            select(ApprovalStep)
            .where(ApprovalStep.flow_id == flow.id)
            .order_by(ApprovalStep.step_order)
        )
        .scalars()
        .all()
    )
    if not steps:
        return _DEFAULT_STEPS

    return [
        {
            "approver_role": s.approver_role,
            "label": s.label or s.approver_role,
            "is_required": s.is_required,
            "can_skip": s.can_skip,
        }
        for s in steps
    ]


def get_report_approval_steps(db: Session) -> list[dict]:
    """获取报工审批流所有步骤"""
    return _load_flow_steps(db)


def get_next_step(db: Session, current_step_index: int) -> dict | None:
    """根据当前已审批次数返回下一步骤，若已全部通过则返回 None"""
    steps = _load_flow_steps(db)
    if current_step_index >= len(steps):
        return None
    step = steps[current_step_index]
    # 若当前步骤可跳过，递归查找下一步
    if step.get("can_skip"):
        return get_next_step(db, current_step_index + 1)
    return step


def get_status_after_approval(db: Session, current_step_index: int) -> str:
    """返回当前步骤审批通过后 Report/ReportUnit 应设置的状态"""
    if current_step_index in _DEFAULT_STATUS_MAP:
        return _DEFAULT_STATUS_MAP[current_step_index]

    steps = _load_flow_steps(db)
    if current_step_index >= len(steps) - 1:
        return "qc_approved"
    return f"step_{current_step_index + 1}_approved"


def is_terminal_status(db: Session, status: str) -> bool:
    """判断是否为终审状态"""
    return status in _TERMINAL_STATUSES


def format_step_label(db: Session, step: dict) -> str:
    """格式化步骤显示标签"""
    return step.get("label") or step.get("approver_role", "未知步骤")