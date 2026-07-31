"""Redis 连接（可选）；不可用时返回 None，验证码等可降级内存。"""

from __future__ import annotations

import redis

from app.core.config import settings

_client: redis.Redis | None | bool = None


def get_redis() -> redis.Redis | None:
    global _client
    if _client is False:
        return None
    if _client is not None:
        return _client
    try:
        c = redis.from_url(settings.REDIS_URL, decode_responses=True)
        c.ping()
        _client = c
        return c
    except Exception:
        _client = False
        return None
