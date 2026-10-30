# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_token
from app.crud.rbac import get_user_permission_codes
from app.models.user import User


security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_token(cred.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已失效")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="登录信息无效")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="账号无效")
    request.state.token_payload = payload
    return user


def get_current_permissions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    cached = getattr(request.state, "permission_codes", None)
    if cached is not None:
        return cached
    codes = get_user_permission_codes(db, user.id)
    request.state.permission_codes = codes
    return codes


def get_optional_permissions(
    request: Request,
    db: Session = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> list[str] | None:
    """可选登录态：无凭据返回 None（由路由级依赖决定 401），有凭据返回权限码。

    用于「路由组已整体要求登录、个别端点还要再按扩展权限收口」的场景，
    避免在测试/内网直连时因为多一层强依赖而 401。
    """
    if not cred or not cred.credentials:
        return None
    try:
        payload = decode_token(cred.credentials)
        user = db.get(User, int(payload.get("sub") or 0))
    except (JWTError, TypeError, ValueError):
        return None
    if not user or not user.is_active:
        return None
    return get_user_permission_codes(db, user.id)


def require_permissions(required: list[str]):
    def _dep(codes: list[str] = Depends(get_current_permissions)) -> None:
        if not set(required).issubset(set(codes)):
            raise HTTPException(status_code=403, detail="无权限")
    return _dep


def require_any_permissions(required: list[str]):
    def _dep(codes: list[str] = Depends(get_current_permissions)) -> None:
        if not set(required) & set(codes):
            raise HTTPException(status_code=403, detail="无权限")
    return _dep


def require_pro(feature: str = "专业版功能"):
    """单版本（纯私有化）交付：不再区分社区版 / 专业版，所有功能默认开放。

    保留该依赖签名以兼容既有路由声明（reports / exec_dashboard），实际不做拦截。
    """
    def _dep() -> None:
        return None
    return _dep

