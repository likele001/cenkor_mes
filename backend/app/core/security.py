from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings


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
