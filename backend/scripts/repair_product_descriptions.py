"""
修复导入时产品 color/spec 列错位导致的描述脏数据。
用法: python3 -m scripts.repair_product_descriptions --tenant-code DEMO
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.product import Product
from app.models.tenant import Tenant
from scripts.import_scanwork_ref import _product_code, parse_insert_rows


def _desc_from_legacy(color, specification) -> str | None:
    parts = []
    if color and str(color).strip() not in ("1", "0", "-"):
        parts.append(f"颜色:{color}")
    spec_s = (specification or "").strip() if specification else ""
    if spec_s and spec_s not in ("1", "0", "-") and not (len(spec_s) <= 2 and spec_s.isdigit()):
        parts.append(f"规格:{spec_s}")
    return "；".join(parts) or None


def run(tenant_code: str, sql_path: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_insert_rows(sql_text, "fa_scanwork_product")
    legacy: dict[str, tuple] = {}
    for row in rows:
        legacy_id = int(row[0])
        name = str(row[2] or "").strip()
        pcode = row[3] if len(row) > 3 else None
        color = row[9] if len(row) > 9 else None
        spec = row[10] if len(row) > 10 else None
        pc = _product_code(legacy_id, pcode, name)
        legacy[pc] = (color, spec)

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
        if not tenant:
            raise SystemExit(f"租户不存在: {tenant_code}")
        products = db.scalars(select(Product).where(Product.tenant_id == tenant.id)).all()
        n = 0
        for p in products:
            if p.code not in legacy:
                continue
            color, spec = legacy[p.code]
            desc = _desc_from_legacy(color, spec)
            if p.description != desc:
                p.description = desc
                n += 1
        db.commit()
        print(f"[REPAIR] 已修正 {n} 条产品描述（租户 {tenant_code}）")
    finally:
        db.close()


def main() -> None:
    default_sql = Path(__file__).resolve().parent.parent.parent / "参考文件.sql"
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-code", default="DEMO")
    ap.add_argument("--sql", type=Path, default=default_sql)
    args = ap.parse_args()
    run(args.tenant_code, args.sql)


if __name__ == "__main__":
    main()
