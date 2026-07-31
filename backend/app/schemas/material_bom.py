from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


BomScope = Literal["sku", "product", "global"]


class MaterialBomItemIn(BaseModel):
    material_id: int = Field(ge=1)
    qty_per: int = Field(ge=0)
    remark: str | None = None


class MaterialBomCreateIn(BaseModel):
    scope: BomScope = "sku"
    sku_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, max_length=128)
    version: int = Field(default=1, ge=1)
    remark: str | None = None
    is_default: bool = False
    items: list[MaterialBomItemIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_scope_fields(self):
        if self.scope == "sku" and not self.sku_id:
            raise ValueError("型号 BOM 必须选择 sku_id")
        if self.scope == "product" and not self.product_id:
            raise ValueError("产品默认 BOM 必须选择 product_id")
        return self


class MaterialBomUpdateIn(BaseModel):
    version: int | None = Field(default=None, ge=1)
    remark: str | None = None
    name: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    is_default: bool | None = None
    items: list[MaterialBomItemIn] | None = None


class MaterialBomCopyToSkuIn(BaseModel):
    sku_id: int = Field(ge=1)


class MaterialBomItemOut(BaseModel):
    id: int
    material_id: int
    material_code: str
    material_name: str
    qty_per: int
    remark: str | None


class MaterialBomOut(BaseModel):
    id: int
    scope: str
    sku_id: int | None
    product_id: int | None
    sku_code: str | None
    sku_name: str | None
    product_code: str | None
    product_name: str | None
    name: str | None
    version: int
    remark: str | None
    is_default: bool
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    items: list[MaterialBomItemOut]
