# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# 币种必须与 app.crud.customer_product.SUPPORTED_CURRENCIES、前端下拉三处一致，
# 漏一个就会出现「下拉能选、保存 422」的隐蔽故障。
CurrencyCode = Literal["CNY", "USD", "EUR", "KRW", "JPY", "HKD", "GBP"]


class CustomerCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    user_id: int | None = Field(default=None, ge=1)
    login_username: str | None = Field(default=None, max_length=64)
    login_password: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool = True
    owner_user_id: int | None = Field(default=None, ge=1)


class CustomerUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    user_id: int | None = Field(default=None, ge=1)
    login_username: str | None = Field(default=None, max_length=64)
    login_password: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool | None = None
    owner_user_id: int | None = Field(default=None, ge=1)


class CustomerProductsSetIn(BaseModel):
    product_ids: list[int] = Field(default_factory=list)


class CustomerProductPricingIn(BaseModel):
    """客户专属价目的一行；price 为该客户购买此产品的单价（按件计）。"""

    product_id: int = Field(ge=1)
    price: Decimal = Field(ge=0, le=Decimal("99999999.9999"))
    min_qty: int = Field(default=1, ge=1, le=1_000_000)
    currency: CurrencyCode = "CNY"


class CustomerProductsPricingSetIn(BaseModel):
    items: list[CustomerProductPricingIn] = Field(default_factory=list)


class CustomerSkuPricingIn(BaseModel):
    """客户型号级价目的一行。

    `price` 传 0 表示删除该型号的覆盖、回落到产品级价目；
    `min_qty` / `currency` 传 null 表示继承产品级（不是取默认值）。
    """

    sku_id: int = Field(ge=1)
    price: Decimal = Field(ge=0, le=Decimal("99999999.9999"))
    min_qty: int | None = Field(default=None, ge=1, le=1_000_000)
    currency: CurrencyCode | None = None


class CustomerSkuPricesSetIn(BaseModel):
    items: list[CustomerSkuPricingIn] = Field(default_factory=list)


class CustomerOut(BaseModel):
    id: int
    user_id: int | None
    owner_user_id: int | None = None
    owner_name: str | None = None
    code: str
    name: str
    contact_name: str | None
    contact_phone: str | None
    address: str | None
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
