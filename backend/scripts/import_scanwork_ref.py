"""
从旧系统 scanwork 导出 SQL（参考文件.sql）导入：
  工序 → 产品 → 型号(SKU) → 型号×工序工价 → 产品默认工艺路线

用法（在 backend 目录）：
  python3 -m scripts.import_scanwork_ref --tenant-code DEMO
  python3 -m scripts.import_scanwork_ref --tenant-code DEMO --sql ../参考文件.sql --dry-run

幂等：以稳定编码 SW-P{id} / SW-M{id} / SW-PR{id} 匹配，重复执行会更新工价、跳过已存在记录。
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.crud.process_price import create_price, get_price_by_sku_process, update_price
from app.crud.process_route import create_route
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.models.product import Product
from app.models.sku import Sku
from app.models.tenant import Tenant
from scripts.scanwork_sql_parser import parse_insert_rows


def log(msg: str) -> None:
    print(f"  [IMPORT] {msg}")


def _product_code(legacy_id: int, product_code: str | None, name: str) -> str:
    base = (product_code or "").strip()
    if base:
        return f"SW-P{legacy_id}-{base}"[:64]
    safe = "".join(c if c.isalnum() or c in "-_" else "" for c in (name or ""))[:20]
    return f"SW-P{legacy_id}-{safe or 'X'}"[:64]


def _sku_code(legacy_id: int, model_code: str | None, name: str) -> str:
    """
    老系统 model_code 常为 -1 / -2 / -3 等内部序号，不是业务型号。
    若直接拼接会得到 SW-M9--2 这类双横线编码，应改用型号名称（如 3+F）。
    """
    mc = (model_code or "").strip()
    if mc in ("-", "0", ""):
        mc = ""
    elif mc.startswith("-") and mc[1:].isdigit():
        mc = ""
    if mc:
        return f"SW-M{legacy_id}-{mc}"[:64]
    safe = "".join(c if c.isalnum() or c in "-_+" else "" for c in (name or ""))[:24]
    return f"SW-M{legacy_id}-{safe or 'X'}"[:64]


def _process_code(legacy_id: int, name: str) -> str:
    safe = "".join(c if c.isalnum() else "" for c in (name or ""))[:16]
    return f"SW-PR{legacy_id}-{safe or 'X'}"[:64]


def get_tenant(db: Session, tenant_code: str) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
    if not t:
        raise SystemExit(f"租户不存在: {tenant_code}")
    return t


def upsert_process(db: Session, tenant_id: int, legacy_id: int, name: str, dry_run: bool) -> int | None:
    code = _process_code(legacy_id, name)
    existing = db.scalar(
        select(Process).where(Process.tenant_id == tenant_id, Process.code == code)
    )
    if existing:
        if existing.name != name and not dry_run:
            existing.name = name
        return existing.id
    if dry_run:
        return -legacy_id
    p = Process(tenant_id=tenant_id, code=code, name=name, workshop=None, std_minutes=None, is_active=True)
    db.add(p)
    db.flush()
    return p.id


def upsert_product(
    db: Session,
    tenant_id: int,
    legacy_id: int,
    name: str,
    product_code: str | None,
    color: str | None,
    specification: str | None,
    dry_run: bool,
) -> int | None:
    code = _product_code(legacy_id, product_code, name)
    existing = db.scalar(select(Product).where(Product.tenant_id == tenant_id, Product.code == code))
    desc_parts = []
    if color and str(color).strip() not in ("1", "0", "-"):
        desc_parts.append(f"颜色:{color}")
    spec_s = (specification or "").strip() if specification else ""
    if spec_s and spec_s not in ("1", "0", "-") and not (len(spec_s) <= 2 and spec_s.isdigit()):
        desc_parts.append(f"规格:{spec_s}")
    description = "；".join(desc_parts) or None
    if existing:
        if not dry_run:
            existing.name = name
            if description:
                existing.description = description
        return existing.id
    if dry_run:
        return -legacy_id
    p = Product(
        tenant_id=tenant_id,
        code=code,
        name=name,
        category=None,
        unit="件",
        description=description,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p.id


def upsert_sku(
    db: Session,
    tenant_id: int,
    product_id: int,
    legacy_id: int,
    name: str,
    model_code: str | None,
    color: str | None,
    specification: str | None,
    fabric_color: str | None,
    description: str | None,
    dry_run: bool,
) -> int | None:
    code = _sku_code(legacy_id, model_code, name)
    existing = db.scalar(select(Sku).where(Sku.tenant_id == tenant_id, Sku.code == code))
    material = fabric_color
    remark = (description or "").strip() or None
    if existing:
        if not dry_run:
            existing.name = name
            existing.product_id = product_id
            existing.color = color
            existing.spec = specification
            existing.material = material
            existing.remark = remark
        return existing.id
    if dry_run:
        return -legacy_id
    s = Sku(
        tenant_id=tenant_id,
        product_id=product_id,
        code=code,
        name=name,
        color=color,
        material=material,
        spec=specification,
        remark=remark,
        is_active=True,
    )
    db.add(s)
    db.flush()
    return s.id


def upsert_price(
    db: Session,
    tenant_id: int,
    sku_id: int,
    process_id: int,
    unit_price: Decimal,
    dry_run: bool,
) -> bool:
    if dry_run:
        return True
    existing = get_price_by_sku_process(db, tenant_id, sku_id, process_id)
    if existing:
        if existing.unit_price != unit_price:
            update_price(db, existing, unit_price=unit_price, is_active=True)
        return False
    create_price(db, tenant_id, sku_id, process_id, unit_price, True)
    return True


def ensure_product_route(
    db: Session,
    tenant_id: int,
    product_id: int,
    process_ids_ordered: list[int],
    dry_run: bool,
) -> None:
    if not process_ids_ordered or dry_run:
        return
    from app.crud.process_route import update_route

    route = db.scalar(
        select(ProcessRoute).where(
            ProcessRoute.tenant_id == tenant_id,
            ProcessRoute.product_id == product_id,
            ProcessRoute.is_default.is_(True),
        )
    )
    steps = [(i + 1, pid) for i, pid in enumerate(process_ids_ordered)]
    if route:
        db.execute(
            ProcessRouteStep.__table__.delete().where(ProcessRouteStep.route_id == route.id)
        )
        db.flush()
        update_route(db, route, steps=steps, is_active=True, is_default=True)
        return
    create_route(db, tenant_id, product_id, "导入默认路线", True, True, steps)


def run(sql_path: Path, tenant_code: str, dry_run: bool) -> None:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    proc_rows = parse_insert_rows(sql_text, "fa_scanwork_process")
    prod_rows = parse_insert_rows(sql_text, "fa_scanwork_product")
    model_rows = parse_insert_rows(sql_text, "fa_scanwork_model")
    price_rows = parse_insert_rows(sql_text, "fa_scanwork_process_price")

    log(f"解析: 工序 {len(proc_rows)}，产品 {len(prod_rows)}，型号 {len(model_rows)}，工价 {len(price_rows)}")

    db = SessionLocal()
    stats = defaultdict(int)
    try:
        tenant = get_tenant(db, tenant_code)
        tid = tenant.id
        log(f"目标租户: {tenant.name} ({tenant.code})")
        if dry_run:
            log("【试运行】不写库")

        # 1. 工序
        proc_map: dict[int, int] = {}
        for row in proc_rows:
            legacy_id = int(row[0])
            name = str(row[9] or "").strip() if len(row) > 9 else ""
            if not name:
                name = f"工序{legacy_id}"
            new_id = upsert_process(db, tid, legacy_id, name, dry_run)
            if new_id:
                proc_map[legacy_id] = new_id
                stats["process"] += 1

        # 2. 产品
        prod_map: dict[int, int] = {}
        for row in prod_rows:
            legacy_id = int(row[0])
            name = str(row[2] or "").strip() or f"产品{legacy_id}"
            product_code = row[3] if len(row) > 3 else None
            # 列顺序: id,factory,name,code,model,route,quality,images,ref,color,spec,status,...
            color = row[9] if len(row) > 9 else None
            specification = row[10] if len(row) > 10 else None
            new_id = upsert_product(db, tid, legacy_id, name, product_code, color, specification, dry_run)
            if new_id:
                prod_map[legacy_id] = new_id
                stats["product"] += 1

        # 3. 型号
        sku_map: dict[int, int] = {}
        sku_to_product: dict[int, int] = {}
        for row in model_rows:
            legacy_id = int(row[0])
            product_legacy = int(row[2])
            name = str(row[3] or "").strip() or f"型号{legacy_id}"
            model_code = row[4] if len(row) > 4 else None
            color = row[5] if len(row) > 5 else None
            specification = row[6] if len(row) > 6 else None
            description = row[8] if len(row) > 8 else None
            fabric_color = row[9] if len(row) > 9 else None
            product_id = prod_map.get(product_legacy)
            if not product_id:
                stats["sku_skip_no_product"] += 1
                log(f"跳过型号 legacy#{legacy_id}：产品 legacy#{product_legacy} 不存在")
                continue
            new_id = upsert_sku(
                db, tid, product_id, legacy_id, name, model_code, color, specification, fabric_color, description, dry_run
            )
            if new_id:
                sku_map[legacy_id] = new_id
                sku_to_product[legacy_id] = product_id
                stats["sku"] += 1

        # 4. 工价 + 收集每产品涉及的工序顺序
        product_processes: dict[int, list[int]] = defaultdict(list)
        seen_pp: set[tuple[int, int]] = set()
        for row in price_rows:
            model_legacy = int(row[2])
            process_legacy = int(row[3])
            price_val = row[4]
            sku_id = sku_map.get(model_legacy)
            process_id = proc_map.get(process_legacy)
            if not sku_id:
                stats["price_skip_no_sku"] += 1
                continue
            if not process_id:
                stats["price_skip_no_process"] += 1
                if stats["price_skip_no_process"] <= 5:
                    log(f"跳过工价：未知工序 legacy#{process_legacy}（型号 legacy#{model_legacy}）")
                continue
            unit_price = Decimal(str(price_val))
            created = upsert_price(db, tid, sku_id, process_id, unit_price, dry_run)
            if created:
                stats["price_new"] += 1
            else:
                stats["price_update"] += 1
            prod_id = sku_to_product.get(model_legacy)
            if prod_id and (prod_id, process_id) not in seen_pp:
                product_processes[prod_id].append(process_id)
                seen_pp.add((prod_id, process_id))

        # 5. 工艺路线（按旧工序 id 排序：扪皮→缝纫→…）
        inv_proc = {nid: lid for lid, nid in proc_map.items()}
        for prod_id, proc_ids in product_processes.items():
            ordered = sorted(proc_ids, key=lambda pid: inv_proc.get(pid, 999))
            ensure_product_route(db, tid, prod_id, ordered, dry_run)
            stats["route"] += 1

        if not dry_run:
            db.commit()
        log("完成统计:")
        for k in sorted(stats.keys()):
            log(f"  {k}: {stats[k]}")
        log(f"映射: 工序 {len(proc_map)}，产品 {len(prod_map)}，型号 {len(sku_map)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    default_sql = Path(__file__).resolve().parent.parent.parent / "参考文件.sql"
    ap = argparse.ArgumentParser(description="从 scanwork 参考 SQL 导入主数据与工价")
    ap.add_argument("--tenant-code", default="DEMO", help="租户编码，默认 DEMO")
    ap.add_argument("--sql", type=Path, default=default_sql, help="SQL 文件路径")
    ap.add_argument("--dry-run", action="store_true", help="仅解析统计，不写数据库")
    args = ap.parse_args()
    if not args.sql.is_file():
        raise SystemExit(f"找不到 SQL 文件: {args.sql}")
    run(args.sql, args.tenant_code, args.dry_run)


if __name__ == "__main__":
    main()
