import re

from pydantic import BaseModel, Field, field_validator


_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm_optional_str(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)

    @field_validator("full_name", "phone", "email", mode="before")
    @classmethod
    def strip_optional(cls, v):
        return _norm_optional_str(v) if isinstance(v, str) else v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _PHONE_RE.match(v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        return v


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
