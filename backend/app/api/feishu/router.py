"""飞书开放平台公开回调（无需登录）"""

from __future__ import annotations

import html as _html

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.feishu.callbacks import handle_feishu_event, parse_event_body
from app.services.feishu.oauth import bind_user_with_code, parse_bind_state
from app.services.feishu.settings import get_feishu_settings_raw

router = APIRouter(tags=["feishu-open"])


def _resolve_encrypt_key(db: Session, body: dict) -> str:
    """单租户版：直接读取唯一的飞书配置"""
    cfg = get_feishu_settings_raw(db)
    return (cfg.get("encrypt_key") or "").strip()


@router.post("/events")
async def feishu_events_api(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    encrypt_key = _resolve_encrypt_key(db, body)
    event = parse_event_body(body, encrypt_key=encrypt_key)
    result = handle_feishu_event(db, event)
    if result:
        return result
    return {}


@router.get("/oauth/callback")
def feishu_oauth_callback_api(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state")
    try:
        user_id = parse_bind_state(state)
        user = bind_user_with_code(db, user_id=user_id, code=code)
        db.commit()
        name = _html.escape(user.full_name or user.username)
        cfg = get_feishu_settings_raw(db)
        app_id = (cfg.get("app_id") or "").strip()
        bot_link = f"https://applink.feishu.cn/client/bot/open?appId={app_id}" if app_id else ""
        h5_base = (cfg.get("h5_public_base_url") or "").strip().rstrip("/")
        bot_btn = (
            f'<p style="margin-top:20px;"><a href="{bot_link}" style="display:inline-block;padding:12px 24px;background:#3370ff;color:#fff;text-decoration:none;border-radius:6px;font-size:16px;">打开 LightMes 机器人（必点）</a></p>'
            if bot_link
            else ""
        )
        bot_hint = (
            "<p style=\"color:#666;margin-top:12px;\">绑定后请<strong>点击上方按钮</strong>打开机器人，并发送任意消息（如「测试」），"
            "个人派工/报工通知才会出现在飞书消息列表。</p>"
        )
        if h5_base:
            redirect_url = f"{h5_base}/profile?feishu_bound=1"
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title>
<meta http-equiv="refresh" content="8;url={redirect_url}"></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>飞书绑定成功</h2><p>{name} 已与飞书账号关联。</p>{bot_btn}{bot_hint}
<p class="text-sm"><a href="{redirect_url}">8 秒后返回个人中心</a></p>
</body></html>"""
        else:
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;max-width:520px;margin:0 auto;">
<h2>飞书绑定成功</h2><p>{name} 已与飞书账号关联。</p>{bot_btn}{bot_hint}
</body></html>"""
        return HTMLResponse(html)
    except Exception as e:
        db.rollback()
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>绑定失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:40px;">
<h2>绑定失败</h2><p>飞书账号绑定过程中发生错误，请稍后重试或联系管理员。</p>
</body></html>"""
        return HTMLResponse(html, status_code=400)
