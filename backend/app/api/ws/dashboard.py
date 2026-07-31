"""大屏 / 看板 WebSocket 推送"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.services.ws_hub import dashboard_ws_hub

router = APIRouter()


def _user_from_token(token: str) -> User | None:
    db: Session = SessionLocal()
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = db.get(User, int(user_id))
        if not user or not user.is_active:
            return None
        return user
    except JWTError:
        return None
    finally:
        db.close()


@router.websocket("/dashboard")
async def dashboard_ws(websocket: WebSocket, token: str = Query(default="")):
    user = _user_from_token(token.strip())
    if not user:
        await websocket.close(code=4401)
        return

    await dashboard_ws_hub.connect(websocket)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
                if msg.strip().lower() in {"ping", '{"type":"ping"}'}:
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "refresh", "channel": "dashboard"})
    except WebSocketDisconnect:
        pass
    finally:
        await dashboard_ws_hub.disconnect(websocket)
