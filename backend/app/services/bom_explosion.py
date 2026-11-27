# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""多级 BOM 展开：半成品（is_sub_assembly）递归展开子 SKU 的 SKU/产品级 BOM。

约定：
- 子级 BOM 只查 SKU 级、产品级，**不回落全厂默认**，否则任意物料都会被误展开；
- 最大深度 10 层，出现环直接报错；
- 半成品无子 BOM 时记录 missing_child_boms，不阻断其它行。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.crud.material_bom import get_strict_bom_for_sku
from app.models.material import Material

MAX_DEPTH = 10


@dataclass
class ExplodedRow:
    material_id: int
    material: Material
    qty: int
    unit_qty: int
    level: int
    path: str
    is_sub_assembly: bool
    child_bom_id: int | None = None
    missing_child_bom: bool = False
    # 仅半成品行：扣掉现有库存后仍需展开的数量
    net_qty: int | None = None


@dataclass
class ExplosionResult:
    rows: list[ExplodedRow] = field(default_factory=list)
    missing_child_boms: list[dict] = field(default_factory=list)


def _walk(
    db: Session,
    *,
    sku_id: int,
    need: int,
    unit_qty: int,
    level: int,
    path: str,
    stack: tuple[int, ...],
    result: ExplosionResult,
    stock_map: dict[int, int] | None,
    bom_cache: dict[int, object],
    max_depth: int,
) -> None:
    if level > max_depth:
        raise ValueError(f"BOM 层级超过 {max_depth} 层，请检查半成品配置")

    if sku_id not in bom_cache:
        bom_cache[sku_id] = get_strict_bom_for_sku(db, sku_id)
    bom = bom_cache[sku_id]
    if bom is None:
        return

    for bi in bom.items:
        m = bi.material
        if not m or not m.is_active:
            continue
        qty = bi.qty_per * need
        row = ExplodedRow(
            material_id=m.id,
            material=m,
            qty=qty,
            unit_qty=bi.qty_per * unit_qty,
            level=level,
            path=f"{path} > {m.code}" if path else m.code,
            is_sub_assembly=bool(bi.is_sub_assembly),
        )
        if not bi.is_sub_assembly:
            result.rows.append(row)
            continue

        child_sku_id = m.sku_id
        if child_sku_id in stack:
            raise ValueError(f"BOM 存在循环引用：{row.path} 又回到上一层半成品")
        if child_sku_id not in bom_cache:
            bom_cache[child_sku_id] = get_strict_bom_for_sku(db, child_sku_id)
        child_bom = bom_cache[child_sku_id]
        if not child_bom:
            row.missing_child_bom = True
            result.missing_child_boms.append(
                {
                    "material_id": m.id,
                    "material_code": m.code,
                    "material_name": m.name,
                    "sku_id": child_sku_id,
                    "level": level,
                }
            )
            result.rows.append(row)
            continue

        row.child_bom_id = child_bom.id
        expand_need = qty
        if stock_map is not None:
            available = max(0, int(stock_map.get(child_sku_id, 0)))
            used = min(available, qty)
            stock_map[child_sku_id] = available - used
            row.net_qty = qty - used
            expand_need = row.net_qty
        result.rows.append(row)
        if expand_need <= 0:
            continue

        _walk(
            db,
            sku_id=child_sku_id,
            need=expand_need,
            unit_qty=bi.qty_per * unit_qty,
            level=level + 1,
            path=row.path,
            stack=(*stack, child_sku_id),
            result=result,
            stock_map=stock_map,
            bom_cache=bom_cache,
            max_depth=max_depth,
        )


def explode_bom(db: Session, sku_id: int, qty: int, *, max_depth: int = MAX_DEPTH) -> ExplosionResult:
    """按毛需求展开（不扣库存），用于齐套展示与层级预览。"""
    result = ExplosionResult()
    if qty <= 0:
        return result
    _walk(
        db,
        sku_id=sku_id,
        need=qty,
        unit_qty=1,
        level=1,
        path="",
        stack=(sku_id,),
        result=result,
        stock_map=None,
        bom_cache={},
        max_depth=max_depth,
    )
    return result


def explode_net(
    db: Session,
    sku_id: int,
    qty: int,
    stock_map: dict[int, int],
    *,
    max_depth: int = MAX_DEPTH,
) -> ExplosionResult:
    """半成品逐层先扣库存，只对剩余量继续展开，用于 MRP 净需求。"""
    result = ExplosionResult()
    if qty <= 0:
        return result
    _walk(
        db,
        sku_id=sku_id,
        need=qty,
        unit_qty=1,
        level=1,
        path="",
        stack=(sku_id,),
        result=result,
        stock_map=stock_map,
        bom_cache={},
        max_depth=max_depth,
    )
    return result


def leaf_rows(result: ExplosionResult) -> list[ExplodedRow]:
    """采购/领料只看叶子物料。"""
    return [r for r in result.rows if not r.is_sub_assembly]


def row_meta(row: ExplodedRow) -> dict:
    m = row.material
    return {
        "material_id": m.id,
        "material_code": m.code,
        "material_name": m.name,
        "unit": m.unit,
        "spec": m.spec,
        "supplier_id": m.supplier_id,
        "sku_id": m.sku_id,
        "level": row.level,
        "path": row.path,
        "is_sub_assembly": row.is_sub_assembly,
        "child_bom_id": row.child_bom_id,
        "missing_child_bom": row.missing_child_bom,
    }
