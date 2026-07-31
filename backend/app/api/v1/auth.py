from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_permissions, get_current_user, get_db
from app.core.response import ok
from app.core.security import create_access_token, token_expire_minutes
from app.crud.user import authenticate, change_user_password, update_user_profile
from app.schemas.auth import LoginIn
from app.schemas.profile import ChangePasswordIn, ProfileUpdateIn
from app.services.login_captcha import assert_login_captcha
from app.services.profile import profile_fields_to_update


router = APIRouter()


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    assert_login_captcha(db, payload.captcha_id, payload.captcha_code)
    user = authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=400, detail="账号或密码错误")
    minutes = token_expire_minutes(payload.remember_me)
    token = create_access_token(
        {"sub": str(user.id), "username": user.username},
        expires_minutes=minutes,
    )
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": minutes * 60,
            "remember_me": payload.remember_me,
        }
    )


def _user_me_out(user, roles: list[str], codes: list[str]) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "roles": roles,
        "permissions": codes,
    }


@router.get("/me")
def me(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    codes: list[str] = Depends(get_current_permissions),
):
    roles = sorted({r.code for r in user.roles})
    return ok(_user_me_out(user, roles, codes))


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    fields = profile_fields_to_update(payload)
    if not fields:
        raise HTTPException(status_code=400, detail="无修改内容")
    update_user_profile(db, user, **fields)
    db.commit()
    db.refresh(user)
    from app.crud.rbac import get_user_permission_codes

    roles = sorted({r.code for r in user.roles})
    codes = get_user_permission_codes(db, user.id)
    return ok(_user_me_out(user, roles, codes))


@router.put("/password")
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        change_user_password(db, user, payload.old_password, payload.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok()
