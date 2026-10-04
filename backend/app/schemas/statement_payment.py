# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class StatementPaymentCreateIn(BaseModel):
    """登记一笔核销（收款/付款）。"""
    amount: Decimal = Field(gt=0, description="本次核销金额，需 > 0 且 <= 未结余额")
    paid_date: date | None = Field(default=None, description="核销日期，缺省今天")
    method: str | None = Field(default=None, max_length=32, description="transfer/cash/acceptance/other")
    remark: str | None = Field(default=None, max_length=500)
