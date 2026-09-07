# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from pydantic import BaseModel, Field


class ApprovalFlowCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    biz_type: str = Field(min_length=1, max_length=32)
    is_active: bool = True


class ApprovalFlowUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None


class ApprovalStepIn(BaseModel):
    step_order: int | None = None
    approver_role: str = Field(min_length=1, max_length=32)
    is_required: bool = True
    can_skip: bool = False
    label: str | None = Field(default=None, max_length=64)


class ApprovalStepsUpdateIn(BaseModel):
    steps: list[ApprovalStepIn]
