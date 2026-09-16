# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""安全响应头中间件：为所有 HTTP 响应用力补充安全头（不覆盖已有值）。"""

# 缺省安全头；优先性：nosniff 防止 MIME 嗅探，frame DENY 防点击劫持，
# Referrer-Policy 控制来源泄露，Permissions-Policy 收敛浏览器能力
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "1; mode=block",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware:
    """纯 ASGI 中间件：仅在 http 响应 start 阶段补充缺失的安全头。

    setdefault 语义：若上游（如 Nginx/CORS）已设置该头则保留原值。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        extra = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                message = {**message, "headers": headers + [kv for kv in extra if kv[0] not in existing]}
            await send(message)

        await self.app(scope, receive, send_wrapper)