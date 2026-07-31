"""主数据对客户/员工端的展示名称（区别于内部编码）"""

from __future__ import annotations

import re


def _parse_product_description(description: str | None) -> tuple[str, str]:
    color = ""
    spec = ""
    for part in (description or "").split("；"):
        part = part.strip()
        if part.startswith("颜色:"):
            color = part[3:].strip()
        elif part.startswith("规格:"):
            spec = part[3:].strip()
    return color, spec


def _is_trivial_attr(text: str) -> bool:
    """过滤导入残留的「1」「0」等无意义规格/颜色占位。"""
    t = (text or "").strip()
    if not t:
        return True
    if t in ("1", "0", "-", "—"):
        return True
    if len(t) <= 2 and t.isdigit():
        return True
    return False


def _is_structured_description(description: str | None) -> bool:
    d = description or ""
    return "颜色:" in d or "规格:" in d


def product_display_name(
    name: str | None,
    description: str | None = None,
    code: str | None = None,
    category: str | None = None,
) -> str:
    """
    产品对外展示名：
    - 名称为主标题（工价、下单、产品库列表均引用）
    - 描述为自由文字时整段追加在名称后
    - 描述为「颜色:…；规格:…」结构化格式时解析后追加
    """
    n = (name or "").strip()
    if n.upper().startswith("SW-P"):
        n = ""

    d = (description or "").strip()
    if d and not _is_structured_description(d):
        if n:
            return f"{n} · {d}" if d != n else n
        return d

    color, spec = _parse_product_description(description)
    if _is_trivial_attr(spec):
        spec = ""
    if _is_trivial_attr(color):
        color = ""

    extras: list[str] = []
    if spec and spec != n:
        extras.append(spec)
    if color and color != n and color not in extras:
        extras.append(color)

    if n:
        return f"{n} · {' · '.join(extras)}" if extras else n

    if extras:
        return " · ".join(extras)

    cat = (category or "").strip()
    if cat:
        return cat

    c = (code or "").strip()
    if c.startswith("SW-P") and "-" in c:
        tail = c.split("-", 2)[-1]
        if not _is_trivial_attr(tail):
            return tail
    return c or "未命名产品"


def sku_display_name(name: str | None, code: str | None = None) -> str:
    """型号对外展示名：用型号名称，不用内部编码。"""
    n = (name or "").strip()
    if n:
        return n
    c = (code or "").strip()
    if c.startswith("SW-M"):
        parts = c.split("-", 2)
        if len(parts) >= 3 and parts[2] and not _is_trivial_attr(parts[2]):
            return parts[2]
    return c or "未命名型号"


def sku_model_label(
    name: str | None,
    code: str | None = None,
    *,
    color: str | None = None,
    material: str | None = None,
    spec: str | None = None,
) -> str:
    """订单/报工用型号展示：名称 + 颜色/规格等属性，不含内部编码。"""
    base = sku_display_name(name, code)
    extras: list[str] = []
    for raw in (color, spec, material):
        t = (raw or "").strip()
        if not t or _is_trivial_attr(t) or t == base:
            continue
        if t not in extras:
            extras.append(t)
    if extras:
        return f"{base} · {' · '.join(extras)}"
    return base


def order_sku_option_label(
    *,
    product_name: str | None,
    product_description: str | None = None,
    product_code: str | None = None,
    product_category: str | None = None,
    sku_name: str | None = None,
    sku_code: str | None = None,
    sku_color: str | None = None,
    sku_material: str | None = None,
    sku_spec: str | None = None,
) -> tuple[str, str, str]:
    """
    返回 (product_display, sku_model_display, combined_label)。
    combined 用于下拉主文案：产品名称 · 型号说明。
    """
    pn = product_display_name(product_name, product_description, product_code, product_category)
    sm = sku_model_label(sku_name, sku_code, color=sku_color, material=sku_material, spec=sku_spec)
    combined = f"{pn} · {sm}" if pn else sm
    return pn, sm, combined


def process_display_name(name: str | None, code: str | None = None) -> str:
    """工序对外展示：工序名称，不用编码作主标题。"""
    n = (name or "").strip()
    if n:
        return n
    return (code or "").strip() or "未命名工序"


def material_display_name(name: str | None, code: str | None = None) -> str:
    n = (name or "").strip()
    if n:
        return n
    return (code or "").strip() or "未命名物料"


def party_display_name(name: str | None, code: str | None = None) -> str:
    """客户/供应商等：名称优先。"""
    n = (name or "").strip()
    if n:
        return n
    return (code or "").strip() or ""


def sku_option_extra_fields(
    *,
    product_name: str | None = None,
    product_description: str | None = None,
    product_code: str | None = None,
    product_category: str | None = None,
    sku_name: str | None = None,
    sku_code: str | None = None,
    sku_color: str | None = None,
    sku_material: str | None = None,
    sku_spec: str | None = None,
) -> dict:
    """SKU 列表/下拉附加字段：product_name、sku_display_name、display_label。"""
    pn, sm, label = order_sku_option_label(
        product_name=product_name,
        product_description=product_description,
        product_code=product_code,
        product_category=product_category,
        sku_name=sku_name,
        sku_code=sku_code,
        sku_color=sku_color,
        sku_material=sku_material,
        sku_spec=sku_spec,
    )
    return {
        "product_name": pn,
        "sku_display_name": sm,
        "display_label": label,
    }
