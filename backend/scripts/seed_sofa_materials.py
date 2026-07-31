"""
沙发厂演示物料导入（参考 thinkmes.sql）
--------------------------------------
运行：
  cd backend
  PYTHONPATH=. python3 scripts/seed_sofa_materials.py
  PYTHONPATH=. python3 scripts/seed_sofa_materials.py --tenant-code DEMO
  PYTHONPATH=. python3 scripts/seed_sofa_materials.py --tenant-code DEMO --with-bom

幂等：已存在的物料编码/供应商/仓库会跳过，仅补库存（若当前为 0 且演示库存>0）。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.crud.material import create_material, get_material_by_code
from app.crud.material_bom import BOM_SCOPE_GLOBAL, create_bom, get_global_default_bom
from app.crud.supplier import create_supplier, get_supplier_by_code
from app.crud.warehouse import adjust_stock, create_warehouse, get_stock
from app.models.material import Material
from app.models.product import Product
from app.models.sku import Sku
from app.models.tenant import Tenant
from scripts.data.sofa_materials import (
    DEMO_BOM_BY_MATERIAL_CODE,
    DEMO_SUPPLIERS,
    DEMO_WAREHOUSES,
    SOFA_MATERIALS,
)


def log(msg: str) -> None:
    print(f"  [MAT] {msg}")


def resolve_tenant(db: Session, tenant_code: str) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
    if not t:
        raise SystemExit(f"租户不存在: {tenant_code}，请先运行 demo_data 或创建租户")
    return t


def seed_suppliers(db: Session, tenant_id: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for code, name, contact, phone in DEMO_SUPPLIERS:
        existing = get_supplier_by_code(db, tenant_id, code)
        if existing:
            out[code] = existing.id
            continue
        s = create_supplier(
            db,
            tenant_id=tenant_id,
            code=code,
            name=name,
            contact_name=contact,
            phone=phone,
            address=None,
            remark="演示数据（thinkmes）",
            is_active=True,
        )
        out[code] = s.id
        log(f"供应商: {name} ({code})")
    return out


def seed_warehouses(db: Session, tenant_id: int) -> dict[str, int]:
    from app.models.warehouse import Warehouse

    out: dict[str, int] = {}
    for code, name, address in DEMO_WAREHOUSES:
        wh = db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.code == code))
        if wh:
            out[code] = wh.id
            continue
        wh = create_warehouse(db, tenant_id=tenant_id, code=code, name=name, address=address)
        out[code] = wh.id
        log(f"仓库: {name} ({code})")
    return out


def seed_materials(
    db: Session,
    tenant_id: int,
    supplier_map: dict[str, int],
    warehouse_id: int,
) -> dict[str, Material]:
    material_map: dict[str, Material] = {}
    created = 0
    stocked = 0
    for code, name, category, unit, spec, stock_qty, sup_code in SOFA_MATERIALS:
        remark = f"分类:{category}（演示数据，来源 thinkmes）"
        existing = get_material_by_code(db, tenant_id, code)
        if existing:
            material_map[code] = existing
            if stock_qty > 0:
                s = get_stock(db, tenant_id, warehouse_id, existing.sku_id)
                if s is None or s.qty == 0:
                    adjust_stock(
                        db,
                        tenant_id=tenant_id,
                        warehouse_id=warehouse_id,
                        sku_id=existing.sku_id,
                        change_qty=stock_qty,
                        biz_type="demo_seed",
                        remark="演示物料期初库存",
                    )
                    stocked += 1
            continue
        sup_id = supplier_map.get(sup_code)
        m = create_material(
            db,
            tenant_id=tenant_id,
            code=code,
            name=name,
            unit=unit,
            spec=spec,
            remark=remark,
            supplier_id=sup_id,
            is_active=True,
        )
        material_map[code] = m
        created += 1
        if stock_qty > 0:
            adjust_stock(
                db,
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                sku_id=m.sku_id,
                change_qty=stock_qty,
                biz_type="demo_seed",
                remark="演示物料期初库存",
            )
            stocked += 1
    log(f"物料: 新增 {created} 条，补库存 {stocked} 条，合计 {len(SOFA_MATERIALS)} 条编码")
    return material_map


def find_demo_product_sku(db: Session, tenant_id: int) -> Sku | None:
    """取第一个非原材料成品型号，用于挂演示 BOM。"""
    mat_product = db.scalar(
        select(Product).where(Product.tenant_id == tenant_id, Product.code == "__MATERIAL__")
    )
    mat_pid = mat_product.id if mat_product else -1
    stmt = (
        select(Sku)
        .where(Sku.tenant_id == tenant_id, Sku.is_active.is_(True), Sku.product_id != mat_pid)
        .order_by(Sku.id.asc())
        .limit(1)
    )
    return db.scalar(stmt)


def seed_demo_bom(db: Session, tenant_id: int, material_map: dict[str, Material]) -> None:
    """创建全厂默认 BOM（同类沙发共用，thinkmes bom_type=1 通用模板）。"""
    if get_global_default_bom(db, tenant_id):
        log("全厂默认 BOM 已存在，跳过")
        return
    items: list[tuple[int, int, str | None]] = []
    for mat_code, qty, item_remark in DEMO_BOM_BY_MATERIAL_CODE:
        m = material_map.get(mat_code)
        if not m:
            m = get_material_by_code(db, tenant_id, mat_code)
        if not m:
            log(f"  跳过 BOM 行：物料 {mat_code} 不存在")
            continue
        items.append((m.id, qty, item_remark))
    if not items:
        log("BOM 明细为空，跳过")
        return
    create_bom(
        db,
        tenant_id=tenant_id,
        scope=BOM_SCOPE_GLOBAL,
        sku_id=None,
        product_id=None,
        name="沙发通用默认BOM",
        version=1,
        remark="演示全厂默认 BOM（参考 thinkmes 通用模板）",
        is_default=True,
        created_by=None,
        items=items,
    )
    log(f"已创建全厂默认 BOM，共 {len(items)} 项；未单独配 BOM 的型号将自动继承")


def run(tenant_code: str, with_bom: bool) -> None:
    db = SessionLocal()
    try:
        tenant = resolve_tenant(db, tenant_code)
        log(f"租户: {tenant.name} ({tenant.code})")
        supplier_map = seed_suppliers(db, tenant.id)
        wh_map = seed_warehouses(db, tenant.id)
        main_wh = wh_map.get("WH001")
        if not main_wh:
            raise SystemExit("主仓库 WH001 创建失败")
        material_map = seed_materials(db, tenant.id, supplier_map, main_wh)
        if with_bom:
            seed_demo_bom(db, tenant.id, material_map)
        db.commit()
        log("✅ 沙发厂演示物料导入完成")
        log(f"   物料 {len(SOFA_MATERIALS)} 种 | 供应商 {len(DEMO_SUPPLIERS)} 家 | 仓库 {len(DEMO_WAREHOUSES)} 个")
        if with_bom:
            log("   已创建全厂默认 BOM，各型号齐套检查将自动继承（个别不同可用「复制到型号」）")
    except Exception as e:
        db.rollback()
        log(f"❌ 失败: {e}")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入沙发厂演示物料（thinkmes 参考）")
    parser.add_argument("--tenant-code", default="DEMO", help="租户编码，默认 DEMO")
    parser.add_argument(
        "--with-bom",
        action="store_true",
        help="为租户下第一个成品型号创建演示 BOM（需已有产品型号）",
    )
    args = parser.parse_args()
    run(args.tenant_code, args.with_bom)


if __name__ == "__main__":
    main()
