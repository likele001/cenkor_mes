from pydantic import BaseModel, Field


class PermissionCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class PermissionUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)


class RoleCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)


class RoleUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=64)


class RoleSetPermissionsIn(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=128)
    is_active: bool = True
    is_superuser: bool = False
    department_id: int | None = None
    role_ids: list[int] = Field(default_factory=list)
    salary_type: str = Field(default="piece", max_length=16, description="piece/hourly/mixed")
    hourly_rate: float | None = Field(default=None, ge=0, description="时薪")


class UserUpdateIn(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    is_superuser: bool | None = None
    department_id: int | None = None
    role_ids: list[int] | None = None
    salary_type: str | None = Field(default=None, max_length=16, description="piece/hourly/mixed")
    hourly_rate: float | None = Field(default=None, ge=0, description="时薪")
