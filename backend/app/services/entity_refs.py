"""API 嵌套对象与下拉项：统一返回展示名，编码仅作辅字段。"""

from __future__ import annotations

from app.services.display_label import (
    material_display_name,
    party_display_name,
    process_display_name,
    product_display_name,
    sku_option_extra_fields,
)


def _product_fields(product) -> dict:
    if not product:
        return {
            "product_name": None,
            "product_description": None,
            "product_code": None,
            "product_category": None,
        }
    return {
        "product_name": product.name,
        "product_description": product.description,
        "product_code": product.code,
        "product_category": product.category,
    }


def missing_bom_dict(sku, product=None) -> dict:
    p = product or getattr(sku, "product", None)
    pf = _product_fields(p)
    extra = sku_option_extra_fields(
        **pf,
        sku_name=sku.name,
        sku_code=sku.code,
        sku_color=getattr(sku, "color", None),
        sku_material=getattr(sku, "material", None),
        sku_spec=getattr(sku, "spec", None),
    )
    return {
        "sku_id": sku.id,
        "sku_code": sku.code,
        "sku_name": extra["sku_display_name"],
        "product_name": extra["product_name"],
        "display_label": extra["display_label"],
    }


def sku_ref_dict(sku, product=None) -> dict | None:
    if not sku:
        return None
    p = product or getattr(sku, "product", None)
    pf = _product_fields(p)
    extra = sku_option_extra_fields(
        **pf,
        sku_name=sku.name,
        sku_code=sku.code,
        sku_color=getattr(sku, "color", None),
        sku_material=getattr(sku, "material", None),
        sku_spec=getattr(sku, "spec", None),
    )
    return {
        "id": sku.id,
        "code": sku.code,
        "name": sku.name,
        "product_id": sku.product_id,
        **extra,
    }


def product_ref_dict(product) -> dict | None:
    if not product:
        return None
    dn = product_display_name(product.name, product.description, product.code, product.category)
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "display_name": dn,
    }


def process_ref_dict(proc) -> dict | None:
    if not proc:
        return None
    dn = process_display_name(proc.name, proc.code)
    return {
        "id": proc.id,
        "code": proc.code,
        "name": proc.name,
        "display_name": dn,
    }


def material_ref_dict(m) -> dict | None:
    if not m:
        return None
    dn = material_display_name(m.name, m.code)
    return {
        "id": m.id,
        "code": m.code,
        "name": m.name,
        "display_name": dn,
    }


def party_ref_dict(p) -> dict | None:
    if not p:
        return None
    dn = party_display_name(p.name, p.code)
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "display_name": dn,
    }


def equipment_ref_dict(eq) -> dict | None:
    if not eq:
        return None
    dn = (eq.name or "").strip() or (eq.code or "").strip()
    return {
        "id": eq.id,
        "code": eq.code,
        "name": eq.name,
        "display_name": dn or "未命名设备",
    }
