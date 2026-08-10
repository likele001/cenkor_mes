"""企业微信回调处理"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_setting import TenantSetting
from app.services.wecom.wxbiz_crypt import OK, WXBizMsgCrypt

logger = logging.getLogger(__name__)


def _iter_wecom_configs(db: Session) -> list[tuple[int, dict]]:
    """单租户版：读取唯一的 wecom.notify 配置（tenant_id 固定为 1）"""
    row = db.scalar(select(TenantSetting).where(TenantSetting.key == "wecom.notify"))
    if not row:
        return []
    try:
        cfg = json.loads(row.value or "{}")
    except Exception:
        return []
    if isinstance(cfg, dict):
        return [(1, cfg)]
    return []


def _build_crypt(cfg: dict) -> WXBizMsgCrypt | None:
    token = (cfg.get("token") or "").strip()
    aes_key = (cfg.get("encoding_aes_key") or "").strip()
    corp_id = (cfg.get("corp_id") or "").strip()
    if not token or not aes_key or not corp_id:
        return None
    try:
        return WXBizMsgCrypt(token, aes_key, corp_id)
    except ValueError:
        return None


def verify_callback_url(
    db: Session,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str | None:
    if not all([msg_signature, timestamp, nonce, echostr]):
        logger.warning("wecom verify missing query params")
        return None
    for tenant_id, cfg in _iter_wecom_configs(db):
        crypt = _build_crypt(cfg)
        if not crypt:
            continue
        ret, reply = crypt.verify_url(msg_signature, timestamp, nonce, echostr)
        if ret == OK and reply:
            logger.info("wecom verify ok tenant_id=%s", tenant_id)
            return reply
        logger.warning("wecom verify failed tenant_id=%s ret=%s", tenant_id, ret)
    return None


def extract_corp_id_from_post(body: str) -> str:
    try:
        root = ET.fromstring(body)
        return (root.findtext("ToUserName") or "").strip()
    except Exception:
        return ""


def decrypt_callback_body(
    db: Session,
    body: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> str | None:
    if not body.strip():
        return None
    corp_id = extract_corp_id_from_post(body)
    candidates = _iter_wecom_configs(db)
    if corp_id:
        candidates = [(tid, cfg) for tid, cfg in candidates if (cfg.get("corp_id") or "").strip() == corp_id]
    for tenant_id, cfg in candidates:
        crypt = _build_crypt(cfg)
        if not crypt:
            continue
        ret, plain = crypt.decrypt_msg(body, msg_signature, timestamp, nonce)
        if ret == OK and plain:
            logger.info("wecom decrypt ok tenant_id=%s", tenant_id)
            return plain
        logger.warning("wecom decrypt failed tenant_id=%s ret=%s", tenant_id, ret)
    return None


def parse_callback_message(body: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(body)
        msg_type = (root.findtext("MsgType") or "").strip()
        return {
            "to_user": root.findtext("ToUserName") or "",
            "from_user": root.findtext("FromUserName") or "",
            "create_time": root.findtext("CreateTime") or "",
            "msg_type": msg_type,
            "content": root.findtext("Content") or "",
            "agent_id": root.findtext("AgentID") or "",
            "msg_id": root.findtext("MsgId") or "",
        }
    except Exception:
        return {}


def _resolve_tenant_id(db: Session, corp_id: str) -> int | None:
    """单租户版：存在 wecom.notify 配置即返回固定 tenant_id=1"""
    rows = db.scalars(select(TenantSetting).where(TenantSetting.key == "wecom.notify")).all()
    return 1 if rows else None


def handle_wecom_event(db: Session, event: dict) -> str | None:
    from app.services.wecom.client import WecomApiError, get_access_token, send_text_message
    from app.services.wecom.settings import get_wecom_credentials

    corp_id = event.get("to_user") or ""
    tenant_id = _resolve_tenant_id(db, corp_id)
    if not tenant_id:
        return None

    from_user = event.get("from_user") or ""
    content = (event.get("content") or "").strip()
    msg_type = event.get("msg_type") or ""

    if msg_type != "text":
        return None

    if not from_user:
        return None

    wecom_corp_id, wecom_secret, agent_id = get_wecom_credentials(db, tenant_id)
    if not wecom_corp_id or not wecom_secret:
        return None

    try:
        token = get_access_token(wecom_corp_id, wecom_secret)

        # Help shortcut
        if content in {"帮助", "help", "?"}:
            reply = "欢迎使用 LightMes 生产通知。\n派工、报工结果、工资提醒会推送到此对话。\n您也可回复「帮助」查看说明。"
        else:
            # Route to AI Employee
            try:
                from app.services.ai_employee.im_dispatch import NO_EMPLOYEE_HINT, dispatch_im_message
                reply = dispatch_im_message(
                    db, tenant_id=tenant_id, channel="wecom",
                    external_user_id=from_user, user_message=content,
                )
                if reply is None:
                    reply = NO_EMPLOYEE_HINT
            except Exception as e:
                logger.error("wecom ai dispatch failed: %s", e)
                reply = "已收到。LightMes 个人通知通道正常，派工/报工消息会推送到此对话。"

        send_text_message(token, from_user, reply, agent_id=agent_id)
    except WecomApiError as e:
        logger.warning("wecom reply failed: %s", e)

    return None
