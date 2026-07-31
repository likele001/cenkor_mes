"""WebSocket 连接池：推送大屏/看板刷新事件"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class DashboardWSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

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

    async def broadcast_all(self, payload: dict[str, Any]) -> None:
        await self.broadcast(payload)


dashboard_ws_hub = DashboardWSHub()
