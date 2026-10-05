# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MrpComputeRequest(BaseModel):
    work_order_ids: list[int]
    remark: str | None = None
    # 限定算哪些仓库的库存；不传＝全部启用中的仓库
    warehouse_ids: list[int] | None = None


class MrpConvertRequest(BaseModel):
    """转采购：不传 item_ids 就把整张计划里还没转的建议行都转掉。"""

    item_ids: list[int] | None = None
    only_with_supplier: bool = True
    remark: str | None = None


class MrpItemOut(BaseModel):
    id: int
    work_order_id: int | None
    order_id: int | None
    sku_id: int
    material_id: int
    bom_id: int | None
    bom_scope: str | None
    wo_qty: int
    qty_per: int
    gross_qty: int
    stock_qty: int
    on_order_qty: int
    net_qty: int
    suggested_purchase_qty: int
    supplier_id: int | None
    unit_price: Decimal | None
    purchase_order_id: int | None

    work_order_code: str | None = None
    order_code: str | None = None
    sku_code: str | None = None
    sku_name: str | None = None
    material_code: str | None = None
    material_name: str | None = None
    material_unit: str | None = None
    supplier_name: str | None = None


class MrpPlanOut(BaseModel):
    id: int
    code: str
    status: str
    source_type: str
    remark: str | None
    total_skus: int
    total_materials: int
    total_purchase_qty: int
    created_by: int | None
    created_at: datetime
    items: list[MrpItemOut] = []


class MrpPlanBrief(BaseModel):
    id: int
    code: str
    status: str
    source_type: str
    total_skus: int
    total_materials: int
    total_purchase_qty: int
    created_at: datetime
