# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings


# 已知不安全/示例密钥：生产环境禁止使用
_INSECURE_SECRETS = {
    "change_me",
    "MUST_CHANGE_ME_in_production",
    "change_me_to_a_long_random_string_at_least_32_chars",
}


def validate_password_strength(password: str) -> None:
    """密码长度策略；不满足时抛出 ValueError。"""
    min_len = int(settings.PASSWORD_MIN_LENGTH)
    if not password or len(password) < min_len:
        raise ValueError(f"密码长度不能少于 {min_len} 位")
    if len(set(password)) < 3:
        raise ValueError("密码过于简单，请使用包含更多不同字符的组合")


def ensure_secure_jwt_secret() -> None:
    """生产环境 fail-fast：JWT 密钥必须是 ≥min 长度的强随机值。"""
    if settings.APP_ENV != "prod":
        return
    secret = settings.JWT_SECRET or ""
    if secret in _INSECURE_SECRETS or len(secret) < int(settings.JWT_SECRET_MIN_LENGTH):
        min_len = int(settings.JWT_SECRET_MIN_LENGTH)
        raise RuntimeError(
            "生产环境 JWT_SECRET 不安全：请设置 ≥%d 位的强随机值（生成命令: "
            "sudo python3 -c \"import secrets;print(secrets.token_urlsafe(48))\"）" % min_len
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def token_expire_minutes(remember_me: bool = False) -> int:
    if remember_me:
        return int(settings.REMEMBER_ME_EXPIRE_MINUTES)
    return int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_access_token(payload: dict[str, Any], expires_minutes: int | None = None, *, remember_me: bool = False) -> str:
    minutes = expires_minutes if expires_minutes is not None else token_expire_minutes(remember_me)
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    to_encode = dict(payload)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
