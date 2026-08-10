"""钉钉配置检查"""

from __future__ import annotations

from app.services.dingtalk.client import DingtalkApiError, get_access_token


def build_setup_check(*, app_key: str, app_secret: str, agent_id: str, oauth_redirect_url: str) -> dict:
    steps = []
    ready = True
    token_ok = False
    try:
        token = get_access_token(app_key, app_secret)
        token_ok = bool(token)
    except DingtalkApiError:
        pass

    steps.append({
        "title": "AppKey / AppSecret 验证",
        "detail": "正常" if token_ok else "请检查 AppKey 和 AppSecret 是否正确",
        "done": token_ok,
    })
    if not token_ok:
        ready = False

    steps.append({
        "title": "AgentId 配置",
        "detail": f"工作通知 AgentId：{agent_id or '未填写'}" if agent_id else "请填写 AgentId（应用详情页）",
        "done": bool(agent_id),
    })
    if not agent_id:
        ready = False

    steps.append({
        "title": "OAuth 回调地址",
        "detail": oauth_redirect_url or "请配置 API 外网地址 PUBLIC_BASE_URL",
        "done": bool(oauth_redirect_url),
    })

    steps.append({
        "title": "应用权限",
        "detail": "开放平台 → 权限管理：通讯录只读、工作通知、手机号获取 userid",
        "done": None,
    })

    return {"ready": ready, "steps": steps}
