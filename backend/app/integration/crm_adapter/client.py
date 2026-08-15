"""CRM webhook 客户端：把 MES 订单状态变化实时回传给 ck_crm。

ck_crm 统一回调入口: POST {crm_base_url}/api/integration/webhook/{connection_id}
body: {"order_code": "...", "status": "producing"}  带 HMAC 签名头。
采用 httpx 同步客户端 + asyncio.to_thread 避免阻塞事件循环，且为尽力而为（失败仅记日志）。
"""
import asyncio
import json
import logging
import time

import httpx

from app.integration.crm_adapter.security import sign


logger = logging.getLogger("crm_adapter")


def _post_sync(url: str, body_bytes: bytes, headers: dict) -> bool:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, content=body_bytes, headers=headers)
        return 200 <= resp.status_code < 300
    except Exception as exc:  # noqa: BLE001
        logger.warning("crm_adapter 状态回传失败: %s -> %s", url, exc)
        return False


async def notify_crm_status(
    crm_base_url: str,
    connection_id: str,
    api_key: str,
    order_code: str,
    status: str,
) -> bool:
    """通知 CRM 某订单的新状态。失败仅记录日志，不抛异常（避免阻塞 MES 业务）。"""
    if not crm_base_url or not connection_id or not api_key:
        logger.warning("crm_adapter 未配置完整，跳过状态回传: order_code=%s", order_code)
        return False
    base = crm_base_url.rstrip("/")
    url = f"{base}/api/integration/webhook/{connection_id}"
    body = json.dumps({"order_code": order_code, "status": status}, ensure_ascii=False)
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": ts,
        "X-Signature": sign(api_key, ts, body),
    }
    ok_result = await asyncio.to_thread(_post_sync, url, body.encode("utf-8"), headers)
    if ok_result:
        logger.info("crm_adapter 状态回传成功: %s -> %s", order_code, status)
    return ok_result
