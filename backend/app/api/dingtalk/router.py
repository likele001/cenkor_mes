"""钉钉回调（公开接口，无需登录）"""

from __future__ import annotations

import html as _html
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.dingtalk.audit_actions import DingtalkAuditError, handle_card_action_token
from app.services.dingtalk.oauth import bind_user_with_code, parse_bind_state
from app.services.dingtalk.settings import get_dingtalk_settings_raw

router = APIRouter(tags=["dingtalk-open"])
logger = logging.getLogger(__name__)


@router.get("/oauth/callback")
def dingtalk_oauth_callback_api(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state")
    try:
        tenant_id, user_id = parse_bind_state(state)
        user = bind_user_with_code(db, tenant_id=tenant_id, user_id=user_id, code=code)
        db.commit()
        name = _html.escape(user.full_name or user.username)
        cfg = get_dingtalk_settings_raw(db, tenant_id)
        h5_base = (cfg.get("h5_public_base_url") or "").strip().rstrip("/")
        if h5_base:
            redirect_url = f"{h5_base}/profile?dingtalk_bound=1"
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title>
<meta http-equiv="refresh" content="5;url={redirect_url}"></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>钉钉绑定成功</h2><p>{name} 已与钉钉账号关联。</p>
<p><a href="{redirect_url}">5 秒后返回个人中心</a></p>
</body></html>"""
        else:
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>钉钉绑定成功</h2><p>{name} 已与钉钉账号关联。</p>
</body></html>"""
        return HTMLResponse(html)
    except Exception as e:
        db.rollback()
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;">
<h2>绑定失败</h2><p>钉钉账号绑定过程中发生错误，请稍后重试或联系管理员。</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)


@router.get("/card-action")
def dingtalk_card_action_api(
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=400, detail="缺少 token")
    try:
        msg = handle_card_action_token(db, token=token)
        db.commit()
        msg = _html.escape(msg)
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>操作成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>操作成功</h2><p>{msg}</p>
</body></html>"""
        return HTMLResponse(html)
    except DingtalkAuditError as e:
        db.rollback()
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>操作失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;">
<h2>操作失败</h2><p>操作处理失败，请稍后重试或联系管理员。</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)
    except Exception as e:
        db.rollback()
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>操作失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;">
<h2>操作失败</h2><p>操作处理发生错误，请稍后重试或联系管理员。</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)


def _resolve_dingtalk_tenant_id(db: Session, app_key: str) -> int | None:
    """单租户版：存在 dingtalk.notify 配置即返回固定 tenant_id=1"""
    import json
    from sqlalchemy import select
    from app.models.tenant_setting import TenantSetting

    rows = db.scalars(select(TenantSetting).where(TenantSetting.key == "dingtalk.notify")).all()
    for row in rows:
        try:
            cfg = json.loads(row.value or "{}")
        except Exception:
            continue
        if (cfg.get("app_key") or "").strip() == app_key:
            return 1
    return 1 if rows else None


@router.post("/robot-message")
async def dingtalk_robot_message_api(request: Request, db: Session = Depends(get_db)):
    """Receive DingTalk robot message callback and route to AI Employee."""
    # Parse request headers for signature verification
    timestamp = request.headers.get("timestamp", "")
    sign = request.headers.get("sign", "")

    body = await request.json()

    # Extract app_key from body for tenant resolution
    # DingTalk sends 'robotCode' or the app_key is embedded in the body
    robot_code = (body.get("robotCode") or body.get("chatbotUserId") or "").strip()

    # Try to resolve tenant by iterating configs to match app_key
    # For now we use a simpler approach: resolve by robot_code or first configured tenant
    from app.services.dingtalk.callbacks import parse_robot_message, verify_robot_signature
    from app.services.dingtalk.settings import get_dingtalk_credentials

    # Resolve tenant_id
    tenant_id = _resolve_dingtalk_tenant_id(db, robot_code)

    if not tenant_id:
        logger.warning("dingtalk robot-message: no tenant found")
        return JSONResponse({"status": "ignored"})

    # Verify signature
    _, app_key, app_secret, agent_id = get_dingtalk_credentials(db, tenant_id)
    if app_secret and not verify_robot_signature(timestamp, sign, app_secret):
        logger.warning("dingtalk robot-message: signature verify failed")
        return JSONResponse({"status": "forbidden"}, status_code=403)

    # Parse message
    msg = parse_robot_message(body)
    sender_id = msg.get("sender_id") or ""
    sender_nick = msg.get("sender_nick") or ""
    text = msg.get("text") or ""
    conv_type = msg.get("conversation_type") or "1"

    if not sender_id or not text:
        return JSONResponse({"status": "ignored"})

    # Route to AI Employee（单租户版未内置 AI 员工，未安装时优雅忽略）
    try:
        from app.services.ai_employee.im_dispatch import NO_EMPLOYEE_HINT, dispatch_im_message
    except ImportError:
        logger.warning("dingtalk robot-message: ai_employee not installed, ignored")
        return JSONResponse({"status": "ignored"})

    reply = dispatch_im_message(
        db, tenant_id=tenant_id, channel="dingtalk",
        external_user_id=sender_id, external_user_name=sender_nick,
        user_message=text,
    )
    if reply is None:
        reply = NO_EMPLOYEE_HINT

    # Send reply via DingTalk robot API
    try:
        from app.services.dingtalk.client import get_access_token, send_robot_reply, send_robot_group_reply, DingtalkApiError
        token = get_access_token(app_key, app_secret)
        if conv_type == "2":
            # Group message
            open_conv_id = body.get("conversationId") or ""
            if open_conv_id:
                send_robot_group_reply(
                    token, robot_code=app_key,
                    open_conversation_id=open_conv_id,
                    msg_key="sampleText",
                    msg_param={"content": reply[:4000]},
                )
        else:
            # P2P message
            send_robot_reply(
                token, robot_code=app_key,
                user_ids=[sender_id],
                msg_key="sampleText",
                msg_param={"content": reply[:4000]},
            )
    except Exception as e:
        logger.error("dingtalk robot reply failed: %s", e)

    return JSONResponse({"status": "ok"})
