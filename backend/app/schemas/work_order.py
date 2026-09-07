# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime

from pydantic import BaseModel


class WorkOrderOut(BaseModel):
    id: int
    order_id: int
    order_item_id: int
    product_id: int
    sku_id: int
    qty: int
    status: str
    created_at: datetime
    updated_at: datetime
