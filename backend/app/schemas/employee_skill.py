from pydantic import BaseModel, Field


class SkillCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    is_active: bool = True


class SkillUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class UserSkillsSetIn(BaseModel):
    skill_ids: list[int] = Field(default_factory=list)
