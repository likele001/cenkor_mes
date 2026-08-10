"""企业微信 API 客户端"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
_ACCESS_TOKEN_KEY = "wecom:access_token:{corpid}"


class WecomApiError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"Wecom API {code}: {msg}")


def _check(resp_data: dict) -> None:
    code = int(resp_data.get("errcode") or 0)
    if code != 0:
        raise WecomApiError(code, str(resp_data.get("errmsg") or "unknown error"))


def get_access_token(corpid: str, corpsecret: str, *, force_refresh: bool = False) -> str:
    """获取企业微信 access_token（Redis 缓存，官方 7200s，提前 5 分钟过期）"""
    r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
    key = _ACCESS_TOKEN_KEY.format(corpid=corpid)
    try:
        if not force_refresh:
            cached = r.get(key)
            if cached:
                return cached
        url = f"{WECOM_API_BASE}/gettoken"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params={"corpid": corpid, "corpsecret": corpsecret})
            resp.raise_for_status()
            data = resp.json()
        _check(data)
        token = data.get("access_token")
        if not token:
            raise WecomApiError(-1, "empty access_token")
        expires_in = int(data.get("expires_in") or 7200)
        r.setex(key, max(expires_in - 300, 300), str(token))
        return str(token)
    finally:
        try:
            r.close()
        except Exception:
            pass


def parse_agent_id(agent_id: str | int | None) -> int:
    try:
        val = int(str(agent_id or "").strip())
    except (TypeError, ValueError):
        raise WecomApiError(-1, "请先配置 Agent ID") from None
    if val <= 0:
        raise WecomApiError(-1, "请先配置 Agent ID")
    return val


def send_text_message(access_token: str, userid: str, content: str, *, agent_id: str | int) -> str:
    url = f"{WECOM_API_BASE}/message/send?access_token={access_token}"
    payload = {
        "touser": userid,
        "msgtype": "text",
        "agentid": parse_agent_id(agent_id),
        "text": {"content": content[:4000]},
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return str(data.get("msgid") or "")


def send_markdown_message(access_token: str, userid: str, content: str, *, agent_id: str | int) -> str:
    url = f"{WECOM_API_BASE}/message/send?access_token={access_token}"
    payload = {
        "touser": userid,
        "msgtype": "markdown",
        "agentid": parse_agent_id(agent_id),
        "markdown": {"content": content[:4000]},
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return str(data.get("msgid") or "")


def send_template_card_message(access_token: str, userid: str, card: dict[str, Any], *, agent_id: str | int) -> str:
    url = f"{WECOM_API_BASE}/message/send?access_token={access_token}"
    payload = {
        "touser": userid,
        "msgtype": "template_card",
        "agentid": parse_agent_id(agent_id),
        "template_card": card,
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return str(data.get("msgid") or "")


def send_webhook_text(webhook_url: str, content: str) -> None:
    if not webhook_url.strip():
        raise WecomApiError(-1, "webhook_url empty")
    payload = {
        "msgtype": "text",
        "text": {"content": content[:4000]},
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(webhook_url.strip(), json=payload)
        resp.raise_for_status()
        data = resp.json()
    _check(data)


def send_webhook_markdown(webhook_url: str, content: str) -> None:
    if not webhook_url.strip():
        raise WecomApiError(-1, "webhook_url empty")
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content[:4000]},
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(webhook_url.strip(), json=payload)
        resp.raise_for_status()
        data = resp.json()
    _check(data)


def get_userid_by_mobile(access_token: str, mobile: str) -> str | None:
    url = f"{WECOM_API_BASE}/user/getuserid?access_token={access_token}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json={"mobile": mobile})
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("errcode") or 0) != 0:
        return None
    userid = data.get("userid")
    if not userid:
        return None
    return str(userid).strip() or None


def batch_get_userid_by_mobiles(access_token: str, mobiles: list[str]) -> list[dict[str, Any]]:
    if not mobiles:
        return []
    results: list[dict[str, Any]] = []
    for mobile in mobiles[:100]:
        uid = get_userid_by_mobile(access_token, mobile)
        results.append({"mobile": mobile, "userid": uid or ""})
    return results


def get_user_info(access_token: str, userid: str) -> dict[str, Any]:
    url = f"{WECOM_API_BASE}/user/get?access_token={access_token}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params={"userid": userid})
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return data


def list_departments(access_token: str, department_id: int = 1) -> list[dict[str, Any]]:
    url = f"{WECOM_API_BASE}/department/list"
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, params={"access_token": access_token, "id": department_id})
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    items: list[dict[str, Any]] = []
    for d in data.get("department") or []:
        items.append({
            "department_id": d.get("id"),
            "name": d.get("name"),
            "parentid": d.get("parentid"),
        })
    return items


def get_agent(access_token: str, agentid: int) -> dict[str, Any]:
    url = f"{WECOM_API_BASE}/agent/get?access_token={access_token}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params={"agentid": agentid})
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return data


def get_webhook_groups(access_token: str) -> list[dict[str, Any]]:
    url = f"{WECOM_API_BASE}/appchat/list?access_token={access_token}"
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, params={"limit": 100, "offset": 0})
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    items: list[dict[str, Any]] = []
    for c in data.get("chatlist") or []:
        items.append({
            "chat_id": c.get("chatid"),
            "name": c.get("name"),
            "owner": c.get("owner"),
        })
    return items


def get_corp_info(access_token: str) -> dict[str, Any]:
    url = f"{WECOM_API_BASE}/corp/get_token_info?access_token={access_token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        if int(data.get("errcode") or 0) == 0:
            return data
    except Exception:
        pass
    return {}


def get_oauth_code_url(corpid: str, redirect_uri: str, state: str) -> str:
    from urllib.parse import quote
    return (
        "https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={quote(corpid)}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&response_type=code"
        f"&scope=snsapi_base"
        f"&state={quote(state)}"
        f"#wechat_redirect"
    )


def get_userinfo_by_code(access_token: str, code: str) -> dict[str, Any]:
    url = f"{WECOM_API_BASE}/user/getuserinfo?access_token={access_token}&code={code}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    _check(data)
    return data
