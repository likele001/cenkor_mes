"""任务报工二维码（打印标签 + 员工端展示）"""

from __future__ import annotations

import re
from urllib.parse import quote

from app.core.config import settings


def build_task_report_url(task_code: str, tenant_code: str | None = None) -> str:
    """
    生成 H5 逐件报工链接（hash 路由）。
    需在 .env 配置 H5_PUBLIC_BASE_URL，例如 https://h5.xxx.com
    未配置时返回纯任务码，供手工输入。
    """
    code = (task_code or "").strip()
    if not code:
        return ""
    base = (getattr(settings, "H5_PUBLIC_BASE_URL", None) or settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return code
    tc = (tenant_code or "").strip().upper()
    q = f"task_code={quote(code, safe='')}"
    if tc:
        q += f"&tenant={quote(tc, safe='')}"
    # 根路径 ?query：index.html 会跳转到 #/report-unit；兼容部分扫码器丢失 hash 后访问 /t/xxx/report-unit
    return f"{base}/?{q}"


def make_qr_svg(text: str) -> str:
    import qrcode
    from qrcode.image.svg import SvgImage

    img = qrcode.make(text, image_factory=SvgImage, box_size=8, border=2)
    buf = __import__("io").BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    svg = re.sub(r"<\?xml[^?]*\?>\s*", "", svg, flags=re.I).strip()
    if svg.startswith("<svg") and "xmlns=" not in svg[:120]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def task_qr_payload(task_code: str, tenant_code: str | None = None) -> dict:
    report_url = build_task_report_url(task_code, tenant_code)
    qr_text = report_url or task_code
    return {
        "task_code": task_code,
        "text": qr_text,
        "report_url": report_url,
        "svg": make_qr_svg(qr_text),
    }
