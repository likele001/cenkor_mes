# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""登录失败限流：按来源 IP 滑动窗口计数，超过阈值后临时锁定。

Redis 优先，Redis 不可用时回退到进程内内存（单实例有效）。
"""
from __future__ import annotations

import time
from threading import Lock

from app.core.config import settings
from app.core.redis_client import get_redis

# 在窗口内累计失败超过阈值即触发锁定
MAX_FAILURES = int(settings.LOGIN_MAX_FAILURES)
WINDOW_SECONDS = int(settings.LOGIN_FAIL_WINDOW_SECONDS)
LOCKOUT_SECONDS = int(settings.LOGIN_LOCKOUT_SECONDS)

_track = "cenkormes:login:fail:"
_block = "cenkormes:login:block:"

_mem: dict[str, tuple[int, float]] = {}   # key -> (fail_count, window_start)
_mem_block: dict[str, float] = {}         # key -> blocked_until
_lock = Lock()


def _safe_ip(client_ip: str | None) -> str:
    return (client_ip or "unknown").strip()


def _blocked_until(ip: str) -> float:
    r = get_redis()
    if r:
        val = r.get(_block + ip)
        try:
            return float(val) if val else 0.0
        except (TypeError, ValueError):
            return 0.0
    with _lock:
        until = _mem_block.get(ip, 0.0)
        if until and until < time.time():
            _mem_block.pop(ip, None)
            until = 0.0
    return until


def is_login_blocked(client_ip: str | None) -> bool:
    ip = _safe_ip(client_ip)
    if not MAX_FAILURES or MAX_FAILURES <= 0:
        return False
    return _blocked_until(ip) > time.time()


def record_login_failure(client_ip: str | None) -> None:
    ip = _safe_ip(client_ip)
    if not MAX_FAILURES or MAX_FAILURES <= 0:
        return
    now = time.time()
    r = get_redis()
    if r:
        key = _track + ip
        pipe = r.pipeline()
        pipe.get(key)
        pipe.get(_block + ip)
        val, blocked = pipe.execute()
        if blocked:
            return
        try:
            count = int(val or "0") + 1
        except (TypeError, ValueError):
            count = 1
        if count >= MAX_FAILURES:
            pipe.set(_block + ip, str(now + LOCKOUT_SECONDS), ex=LOCKOUT_SECONDS)
            pipe.delete(key)
        else:
            pipe.setex(key, WINDOW_SECONDS, str(count))
        pipe.execute()
        return
    with _lock:
        cur = _mem.get(ip)
        if cur and cur[1] + WINDOW_SECONDS > now:
            count = cur[0] + 1
        else:
            count = 1
        if count >= MAX_FAILURES:
            _mem_block[ip] = now + LOCKOUT_SECONDS
            _mem.pop(ip, None)
        else:
            _mem[ip] = (count, now)


def reset_login_failures(client_ip: str | None, username: str | None = None) -> None:
    ip = _safe_ip(client_ip)
    r = get_redis()
    if r:
        r.delete(_track + ip, _block + ip)
        return
    with _lock:
        _mem.pop(ip, None)
        _mem_block.pop(ip, None)