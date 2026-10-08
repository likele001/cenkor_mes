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
    """open-core 授权门控：社区版（IS_PRO=False）访问专业版功能时返回 403。

    专业版构建通过将 app/core/edition.py 的 IS_PRO 置为 True 解锁；
    运行时读取该模块，便于 edition 覆盖后即时生效（需重启后端）。
    """
    def _dep() -> None:
        try:
            from app.core.edition import IS_PRO
        except ImportError:
            IS_PRO = False
        if not IS_PRO:
            raise HTTPException(
                status_code=403,
                detail=f"「{feature}」为专业版(Pro)功能，当前社区版不可用。如需使用请升级专业版或购买对应扩展。",
            )
    return _dep

