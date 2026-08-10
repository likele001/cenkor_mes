"""飞书事件订阅与卡片回调"""

from __future__ import annotations

import base64
import hashlib
import json
import logging

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from sqlalchemy.orm import Session

from app.services.feishu.audit_actions import FeishuAuditError, handle_card_action
from app.services.feishu.client import FeishuApiError, get_tenant_access_token, reply_text_message, send_text_message
from app.services.feishu.settings import get_feishu_credentials
from app.services.feishu.welcome import P2P_ENTER_TEXT, REPLY_ACK_TEXT

logger = logging.getLogger(__name__)


def _decrypt_feishu_event(encrypt_key: str, encrypted: str) -> dict:
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    raw = base64.b64decode(encrypted)
    iv = raw[:16]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plain = decryptor.update(raw[16:]) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plain = unpadder.update(plain) + unpadder.finalize()
    return json.loads(plain.decode("utf-8"))


def parse_event_body(body: dict, *, encrypt_key: str = "") -> dict:
    if body.get("encrypt") and encrypt_key:
        return _decrypt_feishu_event(encrypt_key, str(body["encrypt"]))
    return body


def _message_text(content: str) -> str:
    try:
        data = json.loads(content or "{}")
        return str(data.get("text") or "").strip()
    except Exception:
        return ""


def _sender_open_id(event: dict) -> str:
    sender = event.get("sender") or {}
    sid = sender.get("sender_id") or {}
    return str(sid.get("open_id") or sid.get("user_id") or "").strip()


def _handle_bot_p2p_message(db: Session, event: dict) -> None:
    message = event.get("message") or {}
    if (message.get("message_type") or "") != "text":
        return
    sender_type = (event.get("sender") or {}).get("sender_type") or ""
    if sender_type == "app":
        return
    open_id = _sender_open_id(event)
    if not open_id:
        return
    msg_id = str(message.get("message_id") or "")
    if not msg_id:
        return
    app_id, secret = get_feishu_credentials(db)
    if not app_id or not secret:
        return
    user_text = _message_text(str(message.get("content") or ""))
    # Help shortcut
    if user_text in {"帮助", "help", "?"}:
        reply = P2P_ENTER_TEXT
    else:
        # Route to AI Employee
        try:
            from app.services.ai_employee.im_dispatch import NO_EMPLOYEE_HINT, dispatch_im_message
            reply = dispatch_im_message(
                db, channel="feishu",
                external_user_id=open_id, user_message=user_text,
            )
            if reply is None:
                reply = NO_EMPLOYEE_HINT
        except Exception as e:
            logger.error("feishu ai dispatch failed: %s", e)
            reply = REPLY_ACK_TEXT
    try:
        token = get_tenant_access_token(app_id, secret)
        reply_text_message(access_token=token, message_id=msg_id, text=reply)
    except FeishuApiError as e:
        logger.warning("feishu reply p2p failed: %s", e)


def _handle_bot_p2p_entered(db: Session, event: dict) -> None:
    operator = event.get("operator") or event.get("user") or {}
    open_id = str(operator.get("open_id") or operator.get("operator_id") or "").strip()
    if not open_id:
        return
    app_id, secret = get_feishu_credentials(db)
    if not app_id or not secret:
        return
    try:
        token = get_tenant_access_token(app_id, secret)
        send_text_message(
            access_token=token,
            receive_id=open_id,
            receive_id_type="open_id",
            text=P2P_ENTER_TEXT,
        )
    except FeishuApiError as e:
        logger.warning("feishu p2p enter welcome failed: %s", e)


def handle_feishu_event(db: Session, event: dict) -> dict:
    header = event.get("header") or {}
    event_type = header.get("event_type") or event.get("type") or ""

    if event_type == "url_verification" or event.get("type") == "url_verification":
        return {"challenge": event.get("challenge") or (event.get("event") or {}).get("challenge")}

    if event_type == "card.action.trigger":
        ev = event.get("event") or {}
        action = ev.get("action") or {}
        operator = ev.get("operator") or {}
        open_id = operator.get("open_id") or operator.get("user_id") or ""
        value_raw = action.get("value")
        if isinstance(value_raw, str):
            try:
                value = json.loads(value_raw)
            except Exception:
                value = {"action": value_raw}
        elif isinstance(value_raw, dict):
            value = value_raw
        else:
            value = {}
        action_code = value.get("action") or ""
        biz_type = value.get("biz_type") or ""
        biz_id = int(value.get("biz_id") or 0)
        try:
            msg = handle_card_action(
                db,
                action=action_code,
                biz_type=biz_type,
                biz_id=biz_id,
                operator_open_id=str(open_id),
            )
            db.commit()
            return {
                "toast": {"type": "success", "content": msg[:200]},
                "card": {
                    "type": "raw",
                    "data": {
                        "config": {"wide_screen_mode": True},
                        "elements": [
                            {
                                "tag": "div",
                                "text": {"tag": "plain_text", "content": msg[:500]},
                            }
                        ],
                    },
                },
            }
        except FeishuAuditError as e:
            db.rollback()
            return {"toast": {"type": "error", "content": str(e)[:200]}}
        except Exception as e:
            db.rollback()
            logger.exception("feishu card action failed")
            return {"toast": {"type": "error", "content": str(e)[:200]}}

    ev = event.get("event") or {}
    try:
        if event_type == "im.message.receive_v1":
            _handle_bot_p2p_message(db, ev)
        elif event_type == "im.chat.access_event.bot_p2p_chat_entered_v1":
            _handle_bot_p2p_entered(db, ev)
    except Exception:
        logger.exception("feishu event handler failed type=%s", event_type)

    return {}
