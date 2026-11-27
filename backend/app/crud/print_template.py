# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
import re
from html import escape
from io import BytesIO

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.print_template import PrintTemplate

_BUILTIN_TEMPLATES: dict[str, tuple[str, str, str]] = {}


def get_print_template_by_id(db: Session, template_id: int) -> PrintTemplate | None:
    return db.scalar(select(PrintTemplate).where(PrintTemplate.id == template_id))


def get_print_template_by_code(db: Session, code: str) -> PrintTemplate | None:
    return db.scalar(select(PrintTemplate).where(PrintTemplate.code == code))


def list_print_templates(
    db: Session,
    keyword: str | None = None,
    template_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[PrintTemplate]:
    stmt = select(PrintTemplate)
    if not include_inactive:
        stmt = stmt.where(PrintTemplate.is_active.is_(True))
    if template_type:
        stmt = stmt.where(PrintTemplate.template_type == template_type)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(PrintTemplate.code.like(kw), PrintTemplate.name.like(kw)))
    stmt = stmt.order_by(PrintTemplate.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_print_template(
    db: Session,
    code: str,
    name: str,
    template_type: str,
    content: str,
    is_active: bool,
) -> PrintTemplate:
    item = PrintTemplate(
        code=code,
        name=name,
        template_type=template_type,
        content=content,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def ensure_print_template(db: Session, code: str) -> PrintTemplate | None:
    existing = get_print_template_by_code(db, code)
    if existing and existing.is_active:
        return existing
    builtin = _BUILTIN_TEMPLATES.get(code)
    if not builtin:
        return existing
    name, template_type, content = builtin
    if existing:
        update_print_template(db, existing, name=name, template_type=template_type, content=content, is_active=True)
        return existing
    return create_print_template(
        db,
        code=code,
        name=name,
        template_type=template_type,
        content=content,
        is_active=True,
    )


def update_print_template(
    db: Session,
    item: PrintTemplate,
    code: str | None = None,
    name: str | None = None,
    template_type: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> PrintTemplate:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if template_type is not None:
        item.template_type = template_type
    if content is not None:
        item.content = content
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item


_var_re = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


def render_print_template(content: str, data: dict) -> str:
    def get_value(path: str):
        cur = data
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
                continue
            return ""
        if cur is None:
            return ""
        return str(cur)

    return _var_re.sub(lambda m: get_value(m.group(1)), content)


def html_to_pdf_bytes(html: str) -> bytes:
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise ImportError(
            "PDF 功能依赖未安装。请执行: apt install -y libcairo2-dev pkg-config "
            "然后 pip install -r requirements-pdf.txt"
        ) from e

    bio = BytesIO()
    res = pisa.CreatePDF(html, dest=bio, encoding="utf-8")
    if getattr(res, "err", 0):
        raise ValueError("HTML 转 PDF 失败")
    return bio.getvalue()


def wrap_pdf_html_with_page_number(
    html: str,
    *,
    title: str = "",
    printed_at: str = "",
) -> str:
    style = (
        "@page{size:A4;margin:14mm 12mm 18mm 12mm;"
        "@frame header_frame{-pdf-frame-content:header_content;top:8mm;left:12mm;right:12mm;height:10mm;}"
        "@frame footer_frame{-pdf-frame-content:footer_content;bottom:8mm;left:12mm;right:12mm;height:10mm;}"
        "}"
        "#header_content{font-size:10px;color:#444;}"
        "#footer_content{font-size:10px;color:#444;}"
        ".pdf-page-num{text-align:right;}"
    )

    header_html = escape(title or "")
    printed_at_html = escape(printed_at or "")

    header_block = f'<div id="header_content">{header_html}</div>'
    footer_block = (
        '<div id="footer_content">'
        f'<div style="float:left">{printed_at_html}</div>'
        '<div class="pdf-page-num">第 <pdf:pagenumber /> / <pdf:pagecount /> 页</div>'
        "</div>"
    )

    if "<head" in html.lower():
        if "</head>" in html.lower():
            html = re.sub(r"</head\s*>", f"<style>{style}</style></head>", html, flags=re.I)
        else:
            html = html.replace("<head>", f"<head><style>{style}</style>")
    else:
        html = f"<!doctype html><html><head><meta charset='utf-8'/><style>{style}</style></head>" + html

    if "<body" in html.lower():
        html = re.sub(r"(<body[^>]*>)", r"\1" + header_block + footer_block, html, count=1, flags=re.I)
    else:
        html = html + "<body>" + header_block + footer_block + "</body></html>"

    return html


_DELIVERY_NOTE_HTML = """<html><head><meta charset="utf-8" />
<style>
@page{size:A4;margin:12mm}
body{font-family:Arial,Helvetica,"Microsoft YaHei",sans-serif;font-size:12px;color:#222}
h1{font-size:20px;margin:0 0 4px;text-align:center;letter-spacing:4px}
.sub{text-align:center;color:#666;margin-bottom:10px}
.meta{width:100%;border-collapse:collapse;margin-bottom:8px}
.meta td{padding:4px 6px;border:1px solid #ddd}
.meta td.k{background:#f7f7f7;width:90px;color:#555}
table.items{width:100%;border-collapse:collapse}
table.items th,table.items td{border:1px solid #ccc;padding:6px}
table.items th{background:#f2f2f2;text-align:left}
table.items td.r{text-align:right}
.sign{margin-top:22px;display:flex;justify-content:space-between}
.sign div{width:45%;border-top:1px solid #999;padding-top:6px;color:#555}
</style></head><body>
<h1>送 货 单</h1>
<div class="sub">DELIVERY NOTE</div>
<table class="meta">
<tr><td class="k">发货单号</td><td>{{ shipment.code }}</td><td class="k">订单号</td><td>{{ order.code }}</td></tr>
<tr><td class="k">客户</td><td>{{ customer.name }}</td><td class="k">仓库</td><td>{{ warehouse.name }}</td></tr>
<tr><td class="k">物流公司</td><td>{{ shipment.logistics_company }}</td><td class="k">物流单号</td><td>{{ shipment.logistics_no }}</td></tr>
<tr><td class="k">发货时间</td><td>{{ shipment.shipped_at }}</td><td class="k">签收时间</td><td>{{ shipment.signed_at }}</td></tr>
</table>
<table class="items">
<thead><tr><th>序号</th><th>型号编码</th><th>型号名称</th><th>规格</th><th class="r">数量</th><th>备注</th></tr></thead>
<tbody>{{ items_html }}</tbody>
</table>
<div style="margin-top:8px;text-align:right">合计数量：{{ total_qty }}</div>
<div style="margin-top:6px;color:#555">备注：{{ shipment.remark }}</div>
<div class="sign"><div>发货人签字：</div><div>收货人签字：</div></div>
<div style="margin-top:10px;color:#888">打印时间：{{ printed_at }}</div>
</body></html>"""

# 内置模板：生产环境不依赖 seed_demo，首次打印时由 ensure_print_template 落库
_BUILTIN_TEMPLATES["delivery_note"] = ("送货单", "html", _DELIVERY_NOTE_HTML)
