"""区分成品型号与原材料 SKU（物料挂在 __MATERIAL__ 产品下，编码 MAT- 前缀）"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sku import Sku

MATERIAL_PRODUCT_CODE = "__MATERIAL__"


def is_material_sku_code(code: str | None) -> bool:
    return bool(code) and str(code).strip().upper().startswith("MAT-")


def is_material_product(product: Product | None) -> bool:
    if not product:
        return False
    if (product.code or "").strip() == MATERIAL_PRODUCT_CODE:
        return True
    return (product.category or "").strip().lower() == "material"


def is_finished_product_sku(sku: Sku, product: Product | None = None) -> bool:
    if is_material_sku_code(sku.code):
        return False
    if product is not None:
        return not is_material_product(product)
    return True


def apply_finished_product_sku_filter(stmt):
    """在 Sku 查询上排除原材料型号。"""
    material_pids = select(Product.id).where(
        or_(Product.code == MATERIAL_PRODUCT_CODE, Product.category == "material"),
    )
    return stmt.where(~Sku.code.like("MAT-%"), ~Sku.product_id.in_(material_pids))
