# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""多级 BOM：半成品递归展开、循环拦截、库存净额。"""

import pytest
from sqlalchemy.orm import Session

from app.crud.material_bom import create_bom, validate_sub_assembly
from app.models.material import BOM_SCOPE_SKU, Material, MaterialBom, MaterialBomItem
from app.models.product import Product
from app.models.sku import Sku
from app.services.bom_explosion import explode_bom, explode_net, leaf_rows


def _sku(db: Session, product: Product, code: str) -> Sku:
    s = Sku(product_id=product.id, code=code, name=code, is_active=True)
    db.add(s)
    db.flush()
    return s


def _material(db: Session, sku: Sku, code: str) -> Material:
    m = Material(code=code, name=code, unit="件", sku_id=sku.id)
    db.add(m)
    db.flush()
    return m


def _bom(db: Session, sku: Sku, items: list[tuple]):
    return create_bom(
        db,
        scope=BOM_SCOPE_SKU,
        version=1,
        remark=None,
        created_by=None,
        items=items,
        sku_id=sku.id,
        name=f"BOM-{sku.code}",
    )


@pytest.fixture
def bom_graph(session: Session, product: Product):
    fg_sku = _sku(session, product, "FG")
    sub_sku = _sku(session, product, "SUB")
    leaf_sku = _sku(session, product, "LEAF")
    fg_mat = _material(session, fg_sku, "FG01")
    sub_mat = _material(session, sub_sku, "SUB01")
    leaf_mat = _material(session, leaf_sku, "LEAF01")

    _bom(session, sub_sku, [(leaf_mat.id, 2, None, False)])
    _bom(session, fg_sku, [(sub_mat.id, 3, None, True)])
    return {"fg_sku": fg_sku, "sub_sku": sub_sku, "leaf": leaf_mat, "sub_mat": sub_mat}


def test_explode_two_levels(session: Session, bom_graph):
    result = explode_bom(session, bom_graph["fg_sku"].id, 10)
    leaves = leaf_rows(result)
    assert len(leaves) == 1
    assert leaves[0].material_id == bom_graph["leaf"].id
    assert leaves[0].qty == 60  # 10 × 3 × 2
    assert leaves[0].unit_qty == 6
    assert leaves[0].level == 2
    assert result.missing_child_boms == []


def test_explode_net_deducts_sub_stock(session: Session, bom_graph):
    stock = {bom_graph["sub_sku"].id: 15}  # 需求 30，库存 15
    result = explode_net(session, bom_graph["fg_sku"].id, 10, stock)
    sub_rows = [r for r in result.rows if r.is_sub_assembly]
    assert sub_rows[0].qty == 30
    assert sub_rows[0].net_qty == 15
    assert leaf_rows(result)[0].qty == 30  # 剩余 15 × 2


def test_explode_missing_child_bom(session: Session, product: Product):
    """历史数据可能残留「半成品但子 BOM 已删除」，展开时应记录而非报错。"""
    fg_sku = _sku(session, product, "FG2")
    orphan_sku = _sku(session, product, "ORPHAN")
    orphan = _material(session, orphan_sku, "ORPHAN01")
    bom = MaterialBom(scope=BOM_SCOPE_SKU, sku_id=fg_sku.id, version=1, name="BOM-FG2")
    bom.items = [MaterialBomItem(material_id=orphan.id, qty_per=1, is_sub_assembly=True)]
    session.add(bom)
    session.flush()
    result = explode_bom(session, fg_sku.id, 5)
    assert result.missing_child_boms
    assert result.rows[0].missing_child_bom is True


def test_cycle_rejected(session: Session, product: Product):
    """构造 A→B→A 的脏数据后，保存校验应识别循环。"""
    sku_a = _sku(session, product, "A")
    sku_b = _sku(session, product, "B")
    mat_a = _material(session, sku_a, "MA")
    mat_b = _material(session, sku_b, "MB")
    bom_a = MaterialBom(scope=BOM_SCOPE_SKU, sku_id=sku_a.id, version=1, name="BOM-A")
    bom_a.items = [MaterialBomItem(material_id=mat_b.id, qty_per=1, is_sub_assembly=True)]
    session.add(bom_a)
    session.flush()

    bom_b = MaterialBom(scope=BOM_SCOPE_SKU, sku_id=sku_b.id, version=1, name="BOM-B")
    bom_b.items = [MaterialBomItem(material_id=mat_a.id, qty_per=1, is_sub_assembly=True)]
    session.add(bom_b)
    session.flush()

    with pytest.raises(ValueError, match="循环"):
        validate_sub_assembly(session, [(mat_b.id, 1, None, True)], root_sku_id=sku_a.id)
