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
