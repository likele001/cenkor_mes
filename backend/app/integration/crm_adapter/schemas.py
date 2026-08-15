"""crm_adapter 请求/响应 Pydantic 模型。

OrderItemIn / SalesOrderIn 严格镜像 ck_crm 的 SalesOrderDTO，
保证 CRM 推送的 JSON 能直接被校验接收。
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderItemIn(BaseModel):
    product_name: str = Field(..., description="产品名称")
    spec: str = Field("", description="规格型号")
    quantity: float = Field(..., description="数量")
    unit_price: float = Field(0, description="单价")


class SalesOrderIn(BaseModel):
    order_code: str = Field(..., description="订单编号(CRM 业务单号, 唯一锚点)")
    customer_name: str = Field("", description="客户名称")
    items: list[OrderItemIn] = Field(default_factory=list, description="产品明细")
    delivery_date: str | None = Field(None, description="交期 YYYY-MM-DD")
    remark: str = Field("", description="备注")


class CrmAdapterConfigIn(BaseModel):
    crm_base_url: str = ""
    connection_id: str = ""
    api_key: Optional[str] = None
    status_map: dict[str, str] = Field(default_factory=dict, description="MES状态->CRM标准状态的映射")
    enabled: bool = True
    sign_window: int = 300


class CrmAdapterConfigOut(BaseModel):
    crm_base_url: str = ""
    connection_id: str = ""
    api_key: str = ""
    status_map: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    sign_window: int = 300
    configured: bool = False


class CrmInboundOrderOut(BaseModel):
    id: int
    order_code: str
    customer_name: str
    items: list[dict] = Field(default_factory=list)
    delivery_date: str | None = None
    remark: str = ""
    status: str = "pending"
    mes_order_id: int | None = None
    created_at: Any = None
    updated_at: Any = None


class CrmProductMapIn(BaseModel):
    crm_product_name: str
    crm_spec: str = ""
    mes_sku_id: int


class CrmProductMapOut(BaseModel):
    id: int
    crm_product_name: str
    crm_spec: str
    mes_product_id: int
    mes_sku_id: int
    created_at: Any = None


class StatusUpdateIn(BaseModel):
    status: str = Field(
        ...,
        description="目标状态: pending/producing/part_done/completed/cancelled",
    )
