"""飞书 Open API 客户端"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
_ACCESS_TOKEN_KEY = "feishu:tenant_access_token:{app_id}"


class FeishuApiError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"Feishu API {code}: {msg}")

    @classmethod
    def from_response(cls, data: dict) -> "FeishuApiError":
        code = int(data.get("code", -1))
        msg = str(data.get("msg") or "request failed")
        if code == 99992361 or "cross app" in msg.lower():
            msg = (
                "open_id 与当前 App ID 不匹配（open_id cross app）。"
                "飞书 open_id 按应用隔离，更换 App ID 后必须重新 OAuth 绑定，"
                "或在「人员绑定」用邮箱/手机号重新匹配。"
            )
        elif code == 230013:
            msg = "机器人对该用户不可见，请检查飞书管理后台应用可用范围与展示设置。"
        return cls(code, msg)


def _feishu_request_json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
    except Exception as e:
        raise FeishuApiError(resp.status_code, f"飞书响应非 JSON: HTTP {resp.status_code}") from e
    if int(data.get("code", -1)) != 0:
        raise FeishuApiError.from_response(data)
    return data


def get_tenant_access_token(app_id: str, app_secret: str, *, force_refresh: bool = False) -> str:
    """获取 tenant_access_token（Redis 缓存，飞书默认 7200s，提前 5 分钟过期）"""
    r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
    key = _ACCESS_TOKEN_KEY.format(app_id=app_id)
    try:
        if not force_refresh:
            cached = r.get(key)
            if cached:
                return cached
        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json={"app_id": app_id, "app_secret": app_secret})
            data = _feishu_request_json(resp)
        token = data.get("tenant_access_token")
        if not token:
            raise FeishuApiError(-1, "empty tenant_access_token")
        expires_in = int(data.get("expire") or 7200)
        r.setex(key, max(expires_in - 300, 300), str(token))
        return str(token)
    finally:
        try:
            r.close()
        except Exception:
            pass


def send_interactive_message(
    *,
    access_token: str,
    receive_id: str,
    receive_id_type: str,
    card: dict[str, Any],
) -> str:
    url = f"{FEISHU_API_BASE}/im/v1/messages"
    content = json.dumps(card, ensure_ascii=False)
    payload = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": content,
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, params={"receive_id_type": receive_id_type}, headers=headers, json=payload)
        data = _feishu_request_json(resp)
    msg_id = (data.get("data") or {}).get("message_id") or ""
    return str(msg_id)


def send_webhook_interactive(webhook_url: str, card: dict[str, Any]) -> None:
    if not webhook_url.strip():
        raise FeishuApiError(-1, "webhook_url empty")
    payload = {"msg_type": "interactive", "card": card}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(webhook_url.strip(), json=payload)
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", 0)) not in (0,):
        status = data.get("StatusCode")
        if status is not None and int(status) == 0:
            return
        raise FeishuApiError(int(data.get("code") or -1), str(data.get("msg") or data.get("StatusMessage") or "webhook failed"))


def list_departments(access_token: str, page_size: int = 50) -> list[dict[str, Any]]:
    url = f"{FEISHU_API_BASE}/contact/v3/departments"
    headers = {"Authorization": f"Bearer {access_token}"}
    items: list[dict[str, Any]] = []
    page_token = ""
    with httpx.Client(timeout=20.0) as client:
        while True:
            params: dict[str, Any] = {"page_size": page_size, "department_id_type": "open_department_id"}
            if page_token:
                params["page_token"] = page_token
            resp = client.get(url, headers=headers, params=params)
            data = _feishu_request_json(resp)
            block = data.get("data") or {}
            for row in block.get("items") or []:
                items.append(
                    {
                        "open_department_id": row.get("open_department_id"),
                        "name": row.get("name"),
                        "parent_department_id": row.get("parent_department_id"),
                    }
                )
            if not block.get("has_more"):
                break
            page_token = block.get("page_token") or ""
            if not page_token:
                break
    return items


def send_text_message(
    *,
    access_token: str,
    receive_id: str,
    receive_id_type: str,
    text: str,
) -> str:
    url = f"{FEISHU_API_BASE}/im/v1/messages"
    content = json.dumps({"text": text[:4000]}, ensure_ascii=False)
    payload = {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": content,
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, params={"receive_id_type": receive_id_type}, headers=headers, json=payload)
        data = _feishu_request_json(resp)
    msg_id = (data.get("data") or {}).get("message_id") or ""
    return str(msg_id)


def reply_text_message(*, access_token: str, message_id: str, text: str) -> str:
    url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"
    content = json.dumps({"text": text[:4000]}, ensure_ascii=False)
    payload = {"msg_type": "text", "content": content}
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        data = _feishu_request_json(resp)
    msg_id = (data.get("data") or {}).get("message_id") or ""
    return str(msg_id)


def send_urgent_app(*, access_token: str, message_id: str, open_id: str) -> None:
    if not message_id or not open_id:
        return
    url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/urgent_app"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"user_id_list": [open_id]}
    with httpx.Client(timeout=15.0) as client:
        resp = client.patch(url, headers=headers, params={"user_id_type": "open_id"}, json=payload)
        data = _feishu_request_json(resp)


def send_webhook_text(webhook_url: str, text: str) -> None:
    if not webhook_url.strip():
        raise FeishuApiError(-1, "webhook_url empty")
    payload = {"msg_type": "text", "content": {"text": text[:4000]}}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(webhook_url.strip(), json=payload)
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", 0)) not in (0,):
        status = data.get("StatusCode")
        if status is not None and int(status) == 0:
            return
        raise FeishuApiError(int(data.get("code") or -1), str(data.get("msg") or data.get("StatusMessage") or "webhook failed"))


def list_bot_chats(access_token: str, page_size: int = 50) -> list[dict[str, Any]]:
    url = f"{FEISHU_API_BASE}/im/v1/chats"
    headers = {"Authorization": f"Bearer {access_token}"}
    items: list[dict[str, Any]] = []
    page_token = ""
    with httpx.Client(timeout=20.0) as client:
        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            resp = client.get(url, headers=headers, params=params)
            data = _feishu_request_json(resp)
            block = data.get("data") or {}
            for row in block.get("items") or []:
                items.append(
                    {
                        "chat_id": row.get("chat_id"),
                        "name": row.get("name"),
                        "description": row.get("description"),
                    }
                )
            if not block.get("has_more"):
                break
            page_token = block.get("page_token") or ""
            if not page_token:
                break
    return items


def batch_get_user_id_by_mobiles(access_token: str, mobiles: list[str]) -> list[dict[str, Any]]:
    if not mobiles:
        return []
    url = f"{FEISHU_API_BASE}/contact/v3/users/batch_get_id"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            url,
            params={"user_id_type": "open_id"},
            headers=headers,
            json={"mobiles": mobiles[:50]},
        )
        data = _feishu_request_json(resp)
    return (data.get("data") or {}).get("user_list") or []


def batch_get_open_id_by_emails(access_token: str, emails: list[str]) -> list[dict[str, Any]]:
    if not emails:
        return []
    url = f"{FEISHU_API_BASE}/contact/v3/users/batch_get_id"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            url,
            params={"user_id_type": "open_id"},
            headers=headers,
            json={"emails": emails[:50]},
        )
        data = _feishu_request_json(resp)
    return (data.get("data") or {}).get("user_list") or []
