"""crm_adapter 接口层。

入站（CRM 主动调用，无需登录，HMAC 验签）：
  POST /api/orders                  接收 CRM 推送的标准销售订单
  GET  /api/orders/{order_code}     按业务单号返回当前状态

管理（需登录 + setting.manage 权限）：
  GET  /api/crm-adapter/config      读取对接配置
  PUT  /api/crm-adapter/config      保存对接配置

出站工具（MES 业务代码调用）：
  app.integration.crm_adapter.router.push_status_update(db, order_code, status)
    更新本地记录并把状态实时回传给 CRM。
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permissions
from app.core.response import ok
from app.integration.crm_adapter.client import notify_crm_status
from app.integration.crm_adapter.models import CrmAdapterConfig, CrmInboundOrder, CrmProductMap
from app.integration.crm_adapter.schemas import (
    CrmAdapterConfigIn,
    CrmAdapterConfigOut,
    SalesOrderIn,
    CrmInboundOrderOut,
    StatusUpdateIn,
    CrmProductMapIn,
    CrmProductMapOut,
)
from app.integration.crm_adapter.security import verify_inbound


logger = logging.getLogger("crm_adapter")

CONFIG_ID = 1

inbound_router = APIRouter(tags=["crm-adapter-inbound"])
admin_router = APIRouter(
    tags=["crm-adapter-config"],
    dependencies=[Depends(require_permissions(["setting.manage"]))],
)


def _get_config(db: Session) -> CrmAdapterConfig:
    cfg = db.get(CrmAdapterConfig, CONFIG_ID)
    if cfg is None:
        cfg = CrmAdapterConfig(id=CONFIG_ID)
        db.add(cfg)
        db.flush()
    return cfg


@inbound_router.post("/orders")
async def receive_order(request: Request, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    raw = await verify_inbound(request, cfg.api_key, cfg.sign_window)
    data = SalesOrderIn.model_validate_json(raw)
    items_json = json.dumps([i.model_dump() for i in data.items], ensure_ascii=False)
    existing = db.scalar(
        select(CrmInboundOrder).where(CrmInboundOrder.order_code == data.order_code)
    )
    is_new = existing is None
    if is_new:
        existing = CrmInboundOrder(
            order_code=data.order_code,
            customer_name=data.customer_name,
            items_json=items_json,
            delivery_date=data.delivery_date,
            remark=data.remark,
            status="pending",
            raw_payload=raw,
        )
        db.add(existing)
    else:
        existing.customer_name = data.customer_name
        existing.items_json = items_json
        existing.delivery_date = data.delivery_date
        existing.remark = data.remark
        existing.raw_payload = raw
    db.commit()
    db.refresh(existing)
    logger.info("crm_adapter 收到订单: %s (id=%s)", data.order_code, existing.id)
    return ok({"id": str(existing.id), "order_code": existing.order_code, "mes_order_id": existing.mes_order_id})


@inbound_router.get("/orders/{order_code}")
async def get_order_status(order_code: str, request: Request, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    await verify_inbound(request, cfg.api_key, cfg.sign_window)
    order = db.scalar(
        select(CrmInboundOrder).where(CrmInboundOrder.order_code == order_code)
    )
    if not order:
        return ok({"order_code": order_code, "status": None, "found": False})
    return ok({"order_code": order.order_code, "status": order.status, "found": True})


@admin_router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = _get_config(db)
    try:
        status_map = json.loads(cfg.status_map_json or "{}")
    except Exception:  # noqa: BLE001
        status_map = {}
    configured = bool(cfg.crm_base_url and cfg.connection_id and cfg.api_key)
    return ok(
        CrmAdapterConfigOut(
            crm_base_url=cfg.crm_base_url,
            connection_id=cfg.connection_id,
            api_key="",  # 安全：不返回明文密钥
            status_map=status_map,
            enabled=bool(cfg.enabled),
            sign_window=cfg.sign_window,
            configured=configured,
        ).model_dump()
    )


@admin_router.put("/config")
def save_config(payload: CrmAdapterConfigIn, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    cfg.crm_base_url = payload.crm_base_url.rstrip("/")
    cfg.connection_id = payload.connection_id
    # 仅当显式传入 api_key 时才更新，避免保存其他字段时误清空密钥
    if payload.api_key is not None:
        cfg.api_key = payload.api_key
    cfg.status_map_json = json.dumps(payload.status_map or {}, ensure_ascii=False)
    cfg.enabled = payload.enabled
    cfg.sign_window = payload.sign_window
    db.commit()
    return ok({"saved": True})


@admin_router.get("/orders")
def list_inbound_orders(db: Session = Depends(get_db)):
    """列出 CRM 推送进来的订单（按到达时间倒序）。"""
    rows = db.scalars(
        select(CrmInboundOrder).order_by(desc(CrmInboundOrder.created_at))
    ).all()
    out = []
    for o in rows:
        try:
            items = json.loads(o.items_json or "[]")
        except Exception:  # noqa: BLE001
            items = []
        out.append(
            CrmInboundOrderOut(
                id=o.id,
                order_code=o.order_code,
                customer_name=o.customer_name,
                items=items,
                delivery_date=o.delivery_date,
                remark=o.remark,
                status=o.status,
                mes_order_id=o.mes_order_id,
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
        )
    return ok(out)


_STD_STATUSES = {"pending", "producing", "part_done", "completed", "cancelled"}


@admin_router.post("/orders/{order_code}/status")
def update_inbound_status(
    order_code: str, payload: StatusUpdateIn, db: Session = Depends(get_db)
):
    """修改 CRM 推送订单的状态，并实时回传给 CRM（push_status_update）。"""
    order = db.scalar(
        select(CrmInboundOrder).where(CrmInboundOrder.order_code == order_code)
    )
    if not order:
        return ok({"updated": False, "notified": False, "error": "order_not_found"})
    if payload.status not in _STD_STATUSES:
        return ok({"updated": False, "notified": False, "error": "invalid_status"})
    notified = push_status_update(db, order_code, payload.status)
    return ok(
        {
            "updated": True,
            "notified": bool(notified),
            "status": payload.status,
            "order_code": order_code,
        }
    )


def push_status_update(db: Session, order_code: str, status: str) -> bool:
    """MES 业务侧在订单状态变化时调用。

    更新本地 CRM 推送订单的状态，并按 config.status_map 把 MES 状态
    映射为标准状态后，实时回传给 CRM 的 webhook 入口。
    status 可以是标准码(pending/producing/part_done/completed/cancelled)，
    也可以是 MES 自定义状态(通过配置 status_map 翻译)。
    返回是否成功通知到 CRM。
    """
    order = db.scalar(
        select(CrmInboundOrder).where(CrmInboundOrder.order_code == order_code)
    )
    if not order:
        logger.warning("crm_adapter push_status_update: 未知 order_code=%s", order_code)
        return False
    order.status = status
    db.commit()
    cfg = _get_config(db)
    try:
        status_map = json.loads(cfg.status_map_json or "{}")
    except Exception:  # noqa: BLE001
        status_map = {}
    std_status = status_map.get(status, status)
    try:
        notified = asyncio.run(
            notify_crm_status(
                cfg.crm_base_url, cfg.connection_id, cfg.api_key, order_code, std_status
            )
        )
    except RuntimeError:
        # 极少数已有事件循环的场景, 退化为独立 loop
        loop = asyncio.new_event_loop()
        try:
            notified = loop.run_until_complete(
                notify_crm_status(
                    cfg.crm_base_url, cfg.connection_id, cfg.api_key, order_code, std_status
                )
            )
        finally:
            loop.close()
    return bool(notified)







@admin_router.get("/product-maps")
def list_product_maps(db: Session = Depends(get_db)):
    """列出 CRM 产品名 -> MES SKU 的映射。"""
    rows = db.scalars(select(CrmProductMap).order_by(CrmProductMap.id.desc())).all()
    return ok([
        CrmProductMapOut(
            id=m.id,
            crm_product_name=m.crm_product_name,
            crm_spec=m.crm_spec,
            mes_product_id=m.mes_product_id,
            mes_sku_id=m.mes_sku_id,
            created_at=m.created_at,
        )
        for m in rows
    ])


@admin_router.post("/product-maps")
def create_product_map(payload: CrmProductMapIn, db: Session = Depends(get_db)):
    """新增/更新一条 CRM 产品名 -> MES SKU 映射。"""
    from app.models.sku import Sku
    sku = db.get(Sku, payload.mes_sku_id)
    if sku is None:
        return ok({"created": False, "error": "sku_not_found"})
    existing = db.scalar(
        select(CrmProductMap).where(
            CrmProductMap.crm_product_name == payload.crm_product_name,
            CrmProductMap.crm_spec == (payload.crm_spec or ""),
        ).limit(1)
    )
    if existing:
        existing.mes_product_id = sku.product_id
        existing.mes_sku_id = sku.id
    else:
        existing = CrmProductMap(
            crm_product_name=payload.crm_product_name,
            crm_spec=payload.crm_spec or "",
            mes_product_id=sku.product_id,
            mes_sku_id=sku.id,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return ok({"created": True, "id": existing.id})


@admin_router.delete("/product-maps/{mid}")
def delete_product_map(mid: int, db: Session = Depends(get_db)):
    """删除一条产品映射。"""
    m = db.get(CrmProductMap, mid)
    if not m:
        return ok({"deleted": False, "error": "not_found"})
    db.delete(m)
    db.commit()
    return ok({"deleted": True})
