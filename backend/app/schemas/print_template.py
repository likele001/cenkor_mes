from pydantic import BaseModel, Field


class PrintTemplateCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    template_type: str = Field(default="html", min_length=1, max_length=32)
    content: str = Field(min_length=1)
    is_active: bool = True


class PrintTemplateUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    template_type: str | None = Field(default=None, min_length=1, max_length=32)
    content: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class PrintTemplateRenderIn(BaseModel):
    data: dict = Field(default_factory=dict)
