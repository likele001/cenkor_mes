# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""可观测性基础设施（PERF-1）：结构化访问日志 + 请求关联 ID + SQLAlchemy 慢查询日志。

设计原则：
- 不引入第三方日志库，沿用项目一贯的标准库 logging（见日志系统约定）。
- 纯 ASGI 中间件（与 SecurityHeadersMiddleware 同风格），零 BaseHTTPMiddleware 开销。
- 通过 contextvar 把 request_id 注入日志格式，实现同一请求内跨层关联排障。
- 默认输出到 stdout，被宝塔 nohup 捕获进 error.log，无需额外 sink 配置。
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar

from app.core.config import settings

# 当前请求的关联 ID；未处于请求上下文时为 "-"
REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")

# 专用 logger：propagate=False，独立 handler，避免与 uvicorn root 处理器重复输出
_access_logger = logging.getLogger("app.access")
_sql_logger = logging.getLogger("app.sql")

_LOG_FORMAT = "%(asctime)s %(levelname)s [req=%(request_id)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _RequestIdFilter(logging.Filter):
    """把 contextvar 中的 request_id 注入到每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True


def setup_logging() -> None:
    """初始化访问/慢查询日志处理器（幂等，重复调用不叠加 handler）。"""
    if _access_logger.handlers:
        return
    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    req_filter = _RequestIdFilter()
    for lg in (_access_logger, _sql_logger):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        handler.addFilter(req_filter)
        lg.handlers = [handler]
        lg.setLevel(logging.INFO)
        lg.propagate = False


class RequestContextMiddleware:
    """纯 ASGI 中间件：分配 request_id、计时、输出访问日志、回写 X-Request-ID 头。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = REQUEST_ID.get()
        if rid == "-":  # 每请求生成一个短 ID
            rid = uuid.uuid4().hex[:12]
            REQUEST_ID.set(rid)

        start = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if settings.HTTP_ACCESS_LOG:
                ms = (time.perf_counter() - start) * 1000.0
                client = scope.get("client") or ("-",)
                method = scope.get("method", "-")
                path = scope.get("raw_path", b"").decode("latin-1") or scope.get("path", "-")
                _access_logger.info(
                    "%s %s %s -> %s %.1fms",
                    client[0], method, path, status["code"] or "-", ms,
                )


def _truncate(sql: str, limit: int = 800) -> str:
    sql = " ".join(sql.split())
    return sql if len(sql) <= limit else sql[:limit] + "…"


def enable_slow_query_logging(engine) -> None:
    """在 SQLAlchemy Engine 上注册慢查询监听：单次游标执行耗时超阈值输出 WARNING。"""
    if settings.DB_SLOW_QUERY_MS <= 0:
        return
    from sqlalchemy import event

    threshold = settings.DB_SLOW_QUERY_MS

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        conn.info.setdefault("_cenkor_qtiming", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        stack = conn.info.get("_cenkor_qtiming")
        if not stack:
            return
        t0 = stack.pop()
        ms = (time.perf_counter() - t0) * 1000.0
        if ms >= threshold:
            _sql_logger.warning(
                "慢查询 %.1fms (阈值 %dms, many=%s): %s",
                ms, threshold, executemany, _truncate(statement),
            )
