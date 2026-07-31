from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.notification import create_notification, notify_superusers
from app.crud.salary_slip import ensure_salary_slip, reject_salary_slip, sign_salary_slip
from app.models.user import User


router = APIRouter(prefix="/salary", tags=["h5-salary"])


def _ensure_employee(user: User) -> None:
    roles = {r.code for r in user.roles}
    if not ({"employee", "leader"} & roles):
        raise HTTPException(status_code=403, detail="无权限")


@router.get("/slip")
def my_salary_slip_api(
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    slip = ensure_salary_slip(db,  user_id=user.id, month=month)
    db.commit()
    return ok(
        {
            "id": slip.id,
            "user_id": slip.user_id,
            "month": slip.month,
            "total_qty": slip.total_qty,
            "item_amount": float(slip.item_amount),
            "bonus_amount": float(slip.bonus_amount),
            "deduction_amount": float(slip.deduction_amount),
            "net_amount": float(slip.net_amount),
            "signature_attachment_id": slip.signature_attachment_id,
            "signed_at": slip.signed_at,
            "is_signed": slip.signed_at is not None,
            "confirm_status": slip.confirm_status,
            "reject_reason": slip.reject_reason,
            "rejected_at": slip.rejected_at,
        }
    )


@router.post("/slip/sign")
def sign_my_salary_slip_api(
    attachment_id: int = Query(ge=1),
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    try:
        slip = sign_salary_slip(db,  user_id=user.id, month=month, attachment_id=attachment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    create_notification(
        db,
        user_id=user.id,
        title="工资条已签名确认",
        content=f"{slip.month} 工资条已签名确认",
        level="info",
        biz_type="salary_slip",
        biz_id=slip.id,
    )
    db.commit()
    return ok(
        {
            "id": slip.id,
            "month": slip.month,
            "signature_attachment_id": slip.signature_attachment_id,
            "signed_at": slip.signed_at,
            "confirm_status": slip.confirm_status,
        }
    )


@router.post("/slip/reject")
def reject_my_salary_slip_api(
    reason: str = Query(min_length=1, max_length=255),
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    try:
        slip = reject_salary_slip(db,  user_id=user.id, month=month, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    create_notification(
        db,
        user_id=user.id,
        title="工资条已拒签",
        content=f"{slip.month} 工资条已拒签：{slip.reject_reason}",
        level="warning",
        biz_type="salary_slip",
        biz_id=slip.id,
    )
    notify_superusers(
        db,
        title="有员工拒签工资条",
        content=f"用户 {user.username}({user.id}) 拒签 {slip.month} 工资条：{slip.reject_reason}",
        level="warning",
        biz_type="salary_slip",
        biz_id=slip.id,
    )
    try:
        from app.services.feishu.notify import emit_feishu_event

        emit_feishu_event(
            db,
            "salary.slip_rejected",
            title="有员工拒签工资条",
            content=f"用户 {user.full_name or user.username} 拒签 {slip.month} 工资条：{slip.reject_reason}",
            level="warning",
            biz_type="salary_slip",
            biz_id=slip.id,
            user_id=user.id,
        )
    except Exception:
        pass
    db.commit()
    return ok(
        {
            "id": slip.id,
            "month": slip.month,
            "confirm_status": slip.confirm_status,
            "reject_reason": slip.reject_reason,
            "rejected_at": slip.rejected_at,
        }
    )
