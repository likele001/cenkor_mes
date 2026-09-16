# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AccountSubjectCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    subject_type: Literal["asset", "liability", "equity", "revenue", "cost", "expense"]
    direction: Literal["debit", "credit"] = "debit"
    parent_id: int | None = Field(default=None, ge=1)
    is_active: bool = True
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0)
    remark: str | None = Field(default=None, max_length=500)


class AccountSubjectUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    subject_type: Literal["asset", "liability", "equity", "revenue", "cost", "expense"] | None = None
    direction: Literal["debit", "credit"] | None = None
    parent_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    opening_balance: Decimal | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None, max_length=500)


class VoucherEntryIn(BaseModel):
    account_subject_id: int = Field(ge=1)
    summary: str | None = Field(default=None, max_length=500)
    debit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    party_type: Literal["customer", "supplier", "other"] | None = None
    party_id: int | None = Field(default=None, ge=1)


class VoucherCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    voucher_date: date
    voucher_type: Literal["normal", "receipt", "payment", "transfer"] = "normal"
    summary: str | None = Field(default=None, max_length=500)
    source_type: str | None = Field(default=None, max_length=32)
    source_id: int | None = Field(default=None, ge=1)
    entries: list[VoucherEntryIn] = Field(min_length=2)


class VoucherUpdateIn(BaseModel):
    voucher_date: date | None = None
    voucher_type: Literal["normal", "receipt", "payment", "transfer"] | None = None
    summary: str | None = Field(default=None, max_length=500)
    entries: list[VoucherEntryIn] | None = None


class PeriodClosingIn(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
