"""HMAC-SHA256 双向验签（与 ck_crm MESConnector 完全一致）。

签名: X-Signature = HMAC_SHA256(api_key, f"{X-Timestamp}.{原始body}")
验签: 用收到的原始请求体(不要重新序列化)重算并 compare_digest。
"""
import hashlib
import hmac
import time

from fastapi import HTTPException, Request


def sign(key: str, timestamp: str, body: str = "") -> str:
    msg = f"{timestamp}.{body}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


async def verify_inbound(request: Request, api_key: str, sign_window: int = 300) -> str:
    """校验 CRM 推送请求的 HMAC 签名，返回原始 body 字符串（用于后续解析）。"""
    ts = request.headers.get("X-Timestamp") or request.headers.get("x-timestamp") or ""
    sig = request.headers.get("X-Signature") or request.headers.get("x-signature") or ""
    raw = (await request.body()).decode("utf-8")
    if not api_key:
        raise HTTPException(status_code=403, detail="MES 端未配置 api_key")
    if not ts or not sig:
        raise HTTPException(status_code=403, detail="缺少 X-Timestamp / X-Signature")
    try:
        ts_int = int(ts)
    except ValueError:
        raise HTTPException(status_code=403, detail="X-Timestamp 非法")
    if abs(int(time.time()) - ts_int) > sign_window:
        raise HTTPException(status_code=403, detail="签名时间戳已过期")
    expected = sign(api_key, ts, raw)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="签名校验失败")
    return raw
