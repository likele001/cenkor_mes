# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from typing import Any

from pydantic import BaseModel, Field


class TenantSettingUpsertIn(BaseModel):
    value: Any = Field(default=None)
