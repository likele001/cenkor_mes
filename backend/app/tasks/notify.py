"""飞书 / 企业微信 / 钉钉消息推送 Celery 任务"""
import json
import logging

from celery import shared_task

from app.tasks.decorators import db_task

logger = logging.getLogger(__name__)


# ── 飞书 ────────────────────────────────────────────────────────────────────────

@shared_task(name="feishu.send_message")
def feishu_send_message(log_id: int) -> dict:
    from app.core.db import SessionLocal
    from app.models.feishu_push_log import FeishuPushLog
    from app.services.feishu.cards import build_card
    from app.services.feishu.client import (
        FeishuApiError,
        get_tenant_access_token,
        send_interactive_message,
        send_text_message,
        send_urgent_app,
        send_webhook_interactive,
        send_webhook_text,
    )
    from app.services.feishu.notify import mark_push_log_result
    from app.services.feishu.settings import get_feishu_credentials, get_feishu_settings_raw

    db = SessionLocal()
    try:
        row = db.get(FeishuPushLog, log_id)
        if not row:
            return {"ok": False, "msg": "log_not_found"}
        if row.status == "deferred":
            return {"ok": False, "msg": "deferred"}
        cfg = get_feishu_settings_raw(db)
        payload = {}
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json) or {}
            except Exception:
                payload = {}
        from app.services.feishu.links import build_message_urls

        _gen_h5, _gen_admin = build_message_urls(
            cfg, event_code=row.event_code,
            biz_type=row.biz_type, biz_id=row.biz_id,
            task_code=payload.get("task_code"),
        )
        h5_url = payload.get("h5_url") or _gen_h5
        admin_url = payload.get("admin_url") or _gen_admin
        message_format = payload.get("message_format") or cfg.get("message_format") or "card"
        text = f"{row.title}\n{row.content}"
        try:
            if row.target_kind == "chat":
                webhook = ""
                # 兼容旧顶层结构与迁移后的 channels.feishu 嵌套结构
                for g in cfg.get("groups") or []:
                    if (g.get("chat_id") or "").strip() == row.target_ref:
                        webhook = (g.get("webhook_url") or "").strip()
                        break
                    feishu_ch = (g.get("channels") or {}).get("feishu") or {}
                    if (feishu_ch.get("chat_id") or "").strip() == row.target_ref:
                        webhook = (feishu_ch.get("webhook_url") or "").strip()
                        break
                app_id, secret = get_feishu_credentials(db)
                token = get_tenant_access_token(app_id, secret)
                if message_format == "card":
                    card = build_card(
                        title=row.title, content=row.content, level=row.level,
                        event_code=row.event_code, biz_type=row.biz_type, biz_id=row.biz_id,
                        h5_url=payload.get("h5_url"),
                        admin_url=payload.get("admin_url"), include_audit_actions=False,
                        target_kind="chat",
                    )
                    if webhook:
                        send_webhook_interactive(webhook, card)
                        mark_push_log_result(db, row.id, success=True)
                        db.commit()
                        return {"ok": True, "via": "webhook_interactive"}
                    msg_id = send_interactive_message(
                        access_token=token, receive_id=row.target_ref,
                        receive_id_type="chat_id", card=card,
                    )
                else:
                    if webhook:
                        send_webhook_text(webhook, text)
                        mark_push_log_result(db, row.id, success=True)
                        db.commit()
                        return {"ok": True, "via": "webhook"}
                    msg_id = send_text_message(
                        access_token=token, receive_id=row.target_ref,
                        receive_id_type="chat_id", text=text,
                    )
            else:
                app_id, secret = get_feishu_credentials(db)
                token = get_tenant_access_token(app_id, secret)
                if message_format == "card":
                    card = build_card(
                        title=row.title, content=row.content, level=row.level,
                        event_code=row.event_code, biz_type=row.biz_type, biz_id=row.biz_id,
                        h5_url=payload.get("h5_url"),
                        admin_url=payload.get("admin_url"),
                        include_audit_actions=bool(payload.get("include_audit_actions")),
                        target_kind="user",
                    )
                    msg_id = send_interactive_message(
                        access_token=token, receive_id=row.target_ref,
                        receive_id_type="open_id", card=card,
                    )
                else:
                    msg_id = send_text_message(
                        access_token=token, receive_id=row.target_ref,
                        receive_id_type="open_id", text=text,
                    )
                if row.target_kind == "user" and cfg.get("personal_urgent_enabled"):
                    try:
                        send_urgent_app(access_token=token, message_id=msg_id, open_id=row.target_ref)
                    except FeishuApiError as urgent_err:
                        logger.warning("feishu urgent failed log_id=%s: %s", log_id, urgent_err)
            mark_push_log_result(db, row.id, success=True, message_id=msg_id)
            db.commit()
            return {"ok": True, "message_id": msg_id}
        except FeishuApiError as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e))
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "feishu")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}
        except Exception as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e)[:500])
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "feishu")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)[:500]}
    finally:
        db.close()


@shared_task(name="feishu.flush_deferred")
@db_task
def feishu_flush_deferred(db) -> dict:
    from app.services.feishu.notify import flush_deferred_messages

    n = flush_deferred_messages(db)
    db.commit()
    return {"flushed": n}


# ── 企业微信 ────────────────────────────────────────────────────────────────────

@shared_task(name="wecom.send_message")
def wecom_send_message(log_id: int) -> dict:
    from app.core.db import SessionLocal
    from app.models.wecom_push_log import WecomPushLog
    from app.services.wecom.cards import build_markdown_content, build_text_content  # noqa: F401
    from app.services.wecom.client import (
        WecomApiError,
        get_access_token,
        send_markdown_message,
        send_text_message,
        send_template_card_message,  # noqa: F401
        send_webhook_markdown,
        send_webhook_text,
    )
    from app.services.wecom.notify import mark_push_log_result
    from app.services.wecom.settings import get_wecom_credentials, get_wecom_settings_raw

    db = SessionLocal()
    try:
        row = db.get(WecomPushLog, log_id)
        if not row:
            return {"ok": False, "msg": "log_not_found"}
        if row.status == "deferred":
            return {"ok": False, "msg": "deferred"}
        cfg = get_wecom_settings_raw(db, row.tenant_id)
        payload = {}
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json) or {}
            except Exception:
                payload = {}
        message_format = payload.get("message_format") or cfg.get("message_format") or "markdown"
        text = f"{row.title}\n{row.content}"
        try:
            if row.target_kind == "webhook":
                webhook_url = row.target_ref
                if message_format == "markdown":
                    md_content = build_markdown_content(
                        title=row.title, content=row.content, level=row.level,
                        h5_url=payload.get("h5_url"), admin_url=payload.get("admin_url"),
                    )
                    send_webhook_markdown(webhook_url, md_content)
                else:
                    send_webhook_text(webhook_url, text)
                mark_push_log_result(db, row.id, success=True)
                db.commit()
                return {"ok": True, "via": f"webhook_{message_format}"}
            else:
                corp_id, secret, agent_id = get_wecom_credentials(db, row.tenant_id)
                token = get_access_token(corp_id, secret)
                if message_format == "markdown":
                    md_content = build_markdown_content(
                        title=row.title, content=row.content, level=row.level,
                        h5_url=payload.get("h5_url"), admin_url=payload.get("admin_url"),
                    )
                    msg_id = send_markdown_message(token, row.target_ref, md_content, agent_id=agent_id)
                else:
                    msg_id = send_text_message(token, row.target_ref, text, agent_id=agent_id)
            mark_push_log_result(db, row.id, success=True, message_id=msg_id)
            db.commit()
            return {"ok": True, "message_id": msg_id}
        except WecomApiError as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e))
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "wecom")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}
        except Exception as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e)[:500])
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "wecom")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)[:500]}
    finally:
        db.close()


@shared_task(name="wecom.flush_deferred")
@db_task
def wecom_flush_deferred(db) -> dict:
    from app.services.wecom.notify import flush_deferred_messages

    n = flush_deferred_messages(db)
    db.commit()
    return {"flushed": n}


# ── 钉钉 ────────────────────────────────────────────────────────────────────────

@shared_task(name="dingtalk.send_message")
def dingtalk_send_message(log_id: int) -> dict:
    from app.core.db import SessionLocal
    from app.models.dingtalk_push_log import DingtalkPushLog
    from app.services.dingtalk.cards import build_action_card, build_work_msg_action_card, build_work_msg_markdown  # noqa: F401
    from app.services.dingtalk.client import (
        DingtalkApiError,
        get_access_token,
        send_webhook_action_card,
        send_webhook_text,
        send_work_notification,
    )
    from app.services.dingtalk.notify import mark_push_log_result
    from app.services.dingtalk.settings import get_dingtalk_credentials, get_dingtalk_settings_raw

    db = SessionLocal()
    try:
        row = db.get(DingtalkPushLog, log_id)
        if not row:
            return {"ok": False, "msg": "log_not_found"}
        if row.status == "deferred":
            return {"ok": False, "msg": "deferred"}
        cfg = get_dingtalk_settings_raw(db, row.tenant_id)
        payload = {}
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json) or {}
            except Exception:
                payload = {}
        from app.services.dingtalk.links import build_message_urls

        h5_url, admin_url = build_message_urls(
            cfg, event_code=row.event_code, biz_type=row.biz_type, biz_id=row.biz_id
        )
        h5_url = payload.get("h5_url") or h5_url
        admin_url = payload.get("admin_url") or admin_url
        message_format = payload.get("message_format") or cfg.get("message_format") or "action_card"
        include_audit = bool(
            cfg.get("card_actions_enabled", True)
            and row.event_code == "report.submitted"
            and row.target_kind == "user"
        )
        try:
            if row.target_kind == "webhook":
                secret = payload.get("webhook_secret") or ""
                if message_format == "action_card":
                    card = build_action_card(
                        title=row.title, content=row.content, level=row.level,
                        event_code=row.event_code, biz_type=row.biz_type, biz_id=row.biz_id,
                        tenant_id=row.tenant_id, h5_url=h5_url, admin_url=admin_url,
                        include_audit_actions=False, target_kind="webhook", cfg=cfg,
                    )
                    send_webhook_action_card(row.target_ref, card, secret=secret)
                else:
                    text = f"### {row.title}\n\n{row.content}"
                    if h5_url or admin_url:
                        text += f"\n\n查看详情：{h5_url or admin_url}"
                    send_webhook_text(row.target_ref, text, secret=secret)
                mark_push_log_result(db, row.id, success=True)
                db.commit()
                return {"ok": True, "via": f"webhook_{message_format}"}

            _, app_key, app_secret, agent_id = get_dingtalk_credentials(db, row.tenant_id)
            token = get_access_token(app_key, app_secret)
            dingtalk_userid = payload.get("dingtalk_userid") or row.target_ref
            if message_format == "action_card":
                card = build_action_card(
                    title=row.title, content=row.content, level=row.level,
                    event_code=row.event_code, biz_type=row.biz_type, biz_id=row.biz_id,
                    tenant_id=row.tenant_id, h5_url=h5_url, admin_url=admin_url,
                    include_audit_actions=include_audit, target_kind=row.target_kind,
                    dingtalk_userid=dingtalk_userid, cfg=cfg,
                )
                msg = build_work_msg_action_card(card)
            else:
                msg = build_work_msg_markdown(row.title, row.content, h5_url or admin_url)
            task_id = send_work_notification(token, agent_id=agent_id, userid=row.target_ref, msg=msg)
            mark_push_log_result(db, row.id, success=True, task_id=task_id)
            db.commit()
            return {"ok": True, "task_id": task_id}
        except DingtalkApiError as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e))
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "dingtalk")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}
        except Exception as e:
            mark_push_log_result(db, row.id, success=False, error_msg=str(e)[:500])
            db.commit()
            try:
                from app.services.notify_guard import check_consecutive_failures
                check_consecutive_failures(db, row.event_code, "dingtalk")
                db.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)[:500]}
    finally:
        db.close()


@shared_task(name="dingtalk.flush_deferred")
@db_task
def dingtalk_flush_deferred(db) -> dict:
    from app.services.dingtalk.notify import flush_deferred_messages

    n = flush_deferred_messages(db)
    db.commit()
    return {"flushed": n}


@shared_task(name="push.scan_pending")
@db_task
def push_scan_pending(db) -> dict:
    """补偿扫描：将长时间卡在 pending 的推送日志重新入队。

    场景：进程重启导致 after_commit 回调丢失、或 enqueue 失败仅记 warning，
    造成 push_log 永久 pending。此处扫描 5 分钟前仍为 pending 的日志并重新投递。
    """
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.models.dingtalk_push_log import DingtalkPushLog
    from app.models.feishu_push_log import FeishuPushLog
    from app.models.wecom_push_log import WecomPushLog
    from app.services.notify_dispatcher import _do_send_task

    cutoff = datetime.utcnow() - timedelta(minutes=5)
    reenqueued = 0
    for model, channel in (
        (FeishuPushLog, "feishu"),
        (WecomPushLog, "wecom"),
        (DingtalkPushLog, "dingtalk"),
    ):
        log_ids = db.execute(
            select(model.id)
            .where(model.status == "pending", model.created_at < cutoff)
            .limit(200)
        ).scalars().all()
        for log_id in log_ids:
            _do_send_task(channel, int(log_id))
            reenqueued += 1
    return {"reenqueued": reenqueued}
