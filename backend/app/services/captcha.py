"""图形验证码生成与校验（一次性，Redis 优先）。"""

from __future__ import annotations

import base64
import io
import secrets
import string
import time
from threading import Lock

from PIL import Image, ImageDraw, ImageFont

from app.core.redis_client import get_redis

_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CAPTCHA_TTL = 300
_KEY_PREFIX = "cenkormes:captcha:"

_mem: dict[str, tuple[str, float]] = {}
_mem_lock = Lock()


def _random_code(length: int = 4) -> str:
    return "".join(secrets.choice(_CHARS) for _ in range(length))


def _render_image(code: str) -> bytes:
    w, h = 128, 44
    img = Image.new("RGB", (w, h), (245, 246, 250))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 6), code, fill=(48, 49, 51), font=font)
    for _ in range(6):
        x1, y1 = secrets.randbelow(w), secrets.randbelow(h)
        x2, y2 = secrets.randbelow(w), secrets.randbelow(h)
        draw.line((x1, y1, x2, y2), fill=(200, 200, 210), width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store(captcha_id: str, code: str) -> None:
    norm = code.lower()
    r = get_redis()
    if r:
        r.setex(f"{_KEY_PREFIX}{captcha_id}", _CAPTCHA_TTL, norm)
        return
    expire_at = time.time() + _CAPTCHA_TTL
    with _mem_lock:
        _mem[captcha_id] = (norm, expire_at)


def _pop_expected(captcha_id: str) -> str | None:
    r = get_redis()
    if r:
        key = f"{_KEY_PREFIX}{captcha_id}"
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        got, _ = pipe.execute()
        return str(got).lower() if got else None
    now = time.time()
    with _mem_lock:
        expired = [k for k, (_, exp) in _mem.items() if exp < now]
        for k in expired:
            _mem.pop(k, None)
        row = _mem.pop(captcha_id, None)
    if not row:
        return None
    code, expire_at = row
    if expire_at < now:
        return None
    return code


def create_captcha() -> tuple[str, str, str]:
    """返回 captcha_id, image_base64, expires_in"""
    captcha_id = secrets.token_urlsafe(16)
    code = _random_code()
    _store(captcha_id, code)
    b64 = base64.b64encode(_render_image(code)).decode("ascii")
    return captcha_id, b64, str(_CAPTCHA_TTL)


def verify_captcha(captcha_id: str | None, captcha_code: str | None) -> bool:
    if not captcha_id or not captcha_code:
        return False
    expected = _pop_expected(captcha_id.strip())
    if not expected:
        return False
    return expected == captcha_code.strip().lower()
