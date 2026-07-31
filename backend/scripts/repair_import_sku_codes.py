"""
修复 scanwork 导入产生的异常型号编码（如 SW-M9--2 → SW-M9-3+F）。

用法:
  python3 -m scripts.repair_import_sku_codes --tenant-code DEMO
  python3 -m scripts.repair_import_sku_codes --tenant-code DEMO --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.core.db import SessionLocal
from app.crud.sku import get_sku_by_code
from app.models.sku import Sku
from app.models.tenant import Tenant
from scripts.import_scanwork_ref import _sku_code, parse_insert_rows

_BAD_CODE = re.compile(r"^SW-M(\d+)--\d+$")


def _legacy_model_map(sql_path: Path) -> dict[int, tuple[str, str | None]]:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_insert_rows(sql_text, "fa_scanwork_model")
    out: dict[int, tuple[str, str | None]] = {}
    for row in rows:
        legacy_id = int(row[0])
        name = str(row[3] or "").strip() or f"型号{legacy_id}"
        model_code = str(row[4]).strip() if row[4] is not None and str(row[4]).strip() else None
        out[legacy_id] = (name, model_code)
    return out


def run(tenant_code: str, sql_path: Path, *, dry_run: bool) -> None:
    legacy = _legacy_model_map(sql_path)
    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
        if not tenant:
            raise SystemExit(f"租户不存在: {tenant_code}")
        skus = db.scalars(select(Sku).where(Sku.tenant_id == tenant.id)).all()
        fixed = 0
        skipped = 0
        for s in skus:
            m = _BAD_CODE.match(s.code or "")
            if not m:
                continue
            legacy_id = int(m.group(1))
            name, model_code = legacy.get(legacy_id, (s.name, None))
            new_code = _sku_code(legacy_id, model_code, name)
            if new_code == s.code:
                skipped += 1
                continue
            exists = get_sku_by_code(db, tenant_id=tenant.id, code=new_code)
            if exists and exists.id != s.id:
                print(f"[SKIP] id={s.id} {s.code} -> {new_code} 目标编码已占用")
                skipped += 1
                continue
            print(f"[FIX] id={s.id} {s.code} -> {new_code}  型号名={name}")
            if not dry_run:
                s.code = new_code
            fixed += 1
        if not dry_run:
            db.commit()
        print(f"[REPAIR] 修正 {fixed} 条，跳过 {skipped} 条（租户 {tenant_code}，dry_run={dry_run}）")
    finally:
        db.close()


def main() -> None:
    default_sql = Path(__file__).resolve().parent.parent.parent / "参考文件.sql"
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-code", default="DEMO")
    ap.add_argument("--sql", type=Path, default=default_sql)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.tenant_code, args.sql, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
