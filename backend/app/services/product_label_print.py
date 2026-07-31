"""A4 成品溯源标签批量打印 HTML"""

from __future__ import annotations

from datetime import datetime
from html import escape

from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.product import Product
from app.models.work_order import WorkOrder
from app.models.work_order_piece import WorkOrderPiece
from app.services.trace_public import trace_qr_payload

LABELS_PER_PAGE = 10
COLS = 2


def _label_block(data: dict) -> str:
    import base64
    qr_svg = data["qr"]["svg"]
    qr_b64 = base64.b64encode(qr_svg.encode("utf-8")).decode("ascii")
    qr_data_url = f"data:image/svg+xml;base64,{qr_b64}"
    return f"""
<div class="label">
  <div class="label-inner">
    <div class="qr"><img src="{qr_data_url}" alt="QR" style="width:100%;height:100%;display:block" /></div>
    <div class="info">
      <div class="info-title">📋 产品信息</div>
      <table>
        <tr><td class="k">产品</td><td>{escape(data.get("product_name") or "—")}</td></tr>
        <tr><td class="k">型号</td><td>{escape(data.get("sku_label") or "—")}</td></tr>
        <tr><td class="k">订单</td><td>{escape(data.get("order_name") or "—")}</td></tr>
        <tr><td class="k">套号</td><td>第 {escape(str(data.get("piece_no") or "—"))} 套</td></tr>
        <tr><td class="k">成品码</td><td class="code">{escape(data.get("product_code") or "—")}</td></tr>
      </table>
    </div>
  </div>
</div>
"""


def build_product_trace_labels_html(
    db: Session,
    work_order: WorkOrder,
    pieces: list[WorkOrderPiece],
    *,
    tenant_code: str | None = None,
    title: str = "产品追溯码打印",
) -> str:
    order = db.get(Order, work_order.order_id) if work_order.order_id else None
    sku = work_order.sku
    product = work_order.product or (db.get(Product, sku.product_id) if sku and sku.product_id else None)
    product_name = product.name if product else (sku.name if sku else "")
    sku_label = f"{sku.code} {sku.name}" if sku else ""
    order_name = order.code if order else f"工单#{work_order.id}"

    label_data: list[dict] = []
    for piece in pieces:
        code = piece.product_code or ""
        label_data.append(
            {
                "product_code": code,
                "piece_no": piece.piece_no,
                "product_name": product_name,
                "sku_label": sku_label,
                "order_name": order_name,
                "qr": trace_qr_payload(code, tenant_code),
            }
        )

    pages: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i in range(0, max(len(label_data), 1), LABELS_PER_PAGE):
        chunk = label_data[i : i + LABELS_PER_PAGE]
        header = f"""
<div class="sheet-header">
  <div class="sheet-title">{escape(title)}</div>
  <div class="sheet-meta">生成时间：{now} · 本页 {len(chunk)} 个 · 共 {len(label_data)} 个追溯码</div>
</div>
"""
        labels_html = "".join(_label_block(d) for d in chunk)
        pages.append(f'<div class="sheet">{header}<div class="grid">{labels_html}</div></div>')

    if not label_data:
        pages = [
            f'<div class="sheet"><div class="sheet-header"><div class="sheet-title">{escape(title)}</div>'
            f'<div class="sheet-meta">生成时间：{now} · 暂无可用成品码（请先首道工序派工生成套号池）</div></div></div>'
        ]

    css = """
@page { size: A4; margin: 8mm; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; font-size: 11px; color: #111; }
.sheet { page-break-after: always; }
.sheet:last-child { page-break-after: auto; }
.sheet-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff; padding: 10px 14px; border-radius: 8px; margin-bottom: 8px;
}
.sheet-title { font-size: 18px; font-weight: 700; }
.sheet-meta { font-size: 11px; opacity: 0.92; margin-top: 4px; }
.grid { display: flex; flex-wrap: wrap; gap: 6px; }
.label {
  width: calc(50% - 3px); border: 1px dashed #cbd5e1; border-radius: 8px;
  padding: 6px; min-height: 52mm; page-break-inside: avoid;
}
.label-inner { display: flex; gap: 8px; align-items: flex-start; height: 100%; }
.qr { width: 28mm; min-width: 28mm; height: 28mm; display: flex; align-items: center; justify-content: center; }
.qr img, .qr svg { width: 100%; height: 100%; display: block; object-fit: contain; }
.info { flex: 1; min-width: 0; }
.info-title { font-weight: 700; margin-bottom: 4px; font-size: 12px; }
.info table { width: 100%; border-collapse: collapse; }
.info td { padding: 2px 0; vertical-align: top; line-height: 1.35; }
.info td.k { width: 42px; color: #64748b; white-space: nowrap; }
.info td.code { font-family: monospace; font-size: 10px; word-break: break-all; }
@media print {
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

    body = "\n".join(pages)
    return (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        f"<title>{escape(title)}</title><style>{css}</style></head><body>{body}</body></html>"
    )
