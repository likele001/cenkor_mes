from typing import Any

from pydantic import BaseModel, Field


class TenantSettingUpsertIn(BaseModel):
    value: Any = Field(default=None)
