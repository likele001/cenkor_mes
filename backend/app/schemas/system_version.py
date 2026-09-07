# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date

from pydantic import BaseModel


class SystemVersionOut(BaseModel):
    id: int
    version: str
    release_date: date
    description: str

    model_config = {"from_attributes": True}