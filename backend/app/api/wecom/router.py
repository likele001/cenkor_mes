"""企业微信回调（公开接口，无需登录）"""

from __future__ import annotations

import html as _html
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.wecom.callbacks import (
    decrypt_callback_body,
    handle_wecom_event,
    parse_callback_message,
    verify_callback_url,
)
from app.services.wecom.oauth import bind_user_with_code, parse_bind_state
from app.services.wecom.settings import get_wecom_settings_raw

router = APIRouter(tags=["wecom-open"])
logger = logging.getLogger(__name__)


@router.get("/callback")
def wecom_verify_api(
    msg_signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    echostr: str = Query(default=""),
    db: Session = Depends(get_db),
):
    reply = verify_callback_url(db, msg_signature, timestamp, nonce, echostr)
    if reply is None:
        logger.warning("wecom callback verify rejected")
        raise HTTPException(status_code=403, detail="verify failed")
    return PlainTextResponse(reply)


@router.post("/callback")
async def wecom_callback_api(
    request: Request,
    msg_signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    nonce: str = Query(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()
    body_str = body.decode("utf-8", errors="replace")
    plain = decrypt_callback_body(db, body_str, msg_signature, timestamp, nonce)
    if not plain:
        return PlainTextResponse("success")
    msg = parse_callback_message(plain)
    if not msg:
        return PlainTextResponse("success")
    handle_wecom_event(db, msg)
    db.commit()
    return PlainTextResponse("success")


@router.get("/oauth/callback")
def wecom_oauth_callback_api(
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
        cfg = get_wecom_settings_raw(db, tenant_id)
        h5_base = (cfg.get("h5_public_base_url") or "").strip().rstrip("/")
        if h5_base:
            redirect_url = f"{h5_base}/profile?wecom_bound=1"
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title>
<meta http-equiv="refresh" content="5;url={redirect_url}"></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>企业微信绑定成功</h2><p>{name} 已与企业微信账号关联。</p>
<p><a href="{redirect_url}">5 秒后返回个人中心</a></p>
</body></html>"""
        else:
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>企业微信绑定成功</h2><p>{name} 已与企业微信账号关联。</p>
</body></html>"""
        return HTMLResponse(html)
    except Exception as e:
        db.rollback()
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;">
<h2>绑定失败</h2><p>企业微信账号绑定过程中发生错误，请稍后重试或联系管理员。</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)
