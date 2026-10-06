# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""WebSocket 连接池：推送大屏/看板刷新事件

生产者在同步代码里（线程池中的 FastAPI 端点、脚本），消费者在事件循环里，
因此广播必须经 run_coroutine_threadsafe 回主循环。

连接池是进程内存态：多 worker 部署时每台只有自己连接的客户端能看到自己的
提交，跨进程需要换成 Redis pub/sub。当前 :8500 单进程，先不做这层。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Iterable

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# 连续提交（批量派工、自动化排产一次 commit 几十次）不该让大屏重载几十遍
REFRESH_COALESCE_SECONDS = 3.0


class DashboardWSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # 同步侧状态：可能来自多个线程，用 threading.Lock 保护
        self._sync = threading.Lock()
        self._pending_channels: set[str] = set()
        self._last_flush_at = 0.0
        self._flush_handle: asyncio.TimerHandle | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._clients)
        if not targets:
            return
        text = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def publish(self, payload: dict[str, Any]) -> None:
        """从任意线程投递一条消息，绝不抛出（推送失败不该拖垮业务写入）。"""
        loop = self._loop
        if loop is None or not self._clients or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), loop)
        except RuntimeError as e:
            logger.debug("ws publish skipped: %s", e)

    def publish_refresh(
        self,
        channels: Iterable[str] = (),
        *,
        reason: str = "",
        coalesce: bool = True,
    ) -> bool:
        """投递看板刷新事件；返回是否立刻发出（False = 已合并或无人订阅）。

        coalesce 窗口内的多次变更先累计 channel，窗口结束再补发一次，
        保证最后一次改动一定会被大屏看到。
        """
        if not self._clients:
            return False
        names = {c for c in channels if c} or {"dashboard"}
        now = time.monotonic()
        with self._sync:
            self._pending_channels |= names
            wait = self._last_flush_at + REFRESH_COALESCE_SECONDS - now
            if not coalesce or wait <= 0:
                return self._flush_locked(now, reason)
            self._schedule_flush_locked(wait, reason)
            return False

    def _schedule_flush_locked(self, delay: float, reason: str) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        # 总是重挂：旧 handle 可能属于一个已经关闭的 loop，留着它就再没人补发了
        self._flush_handle = None
        try:
            self._flush_handle = loop.call_later(
                delay, lambda: self.publish_refresh_scheduled(reason)
            )
        except RuntimeError as e:
            logger.debug("ws coalesce schedule skipped: %s", e)

    def publish_refresh_scheduled(self, reason: str = "coalesced") -> None:
        """合并窗口到期后的补发（由事件循环回调触发）。"""
        with self._sync:
            self._flush_handle = None
            self._flush_locked(time.monotonic(), reason)

    def _flush_locked(self, now: float, reason: str) -> bool:
        if not self._pending_channels:
            return False
        payload: dict[str, Any] = {
            "type": "refresh",
            "channel": "dashboard",
            "changed": sorted(self._pending_channels),
        }
        if reason:
            payload["reason"] = reason
        self._pending_channels = set()
        self._last_flush_at = now
        self.publish(payload)
        return True


dashboard_ws_hub = DashboardWSHub()
