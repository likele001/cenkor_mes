"""
预置打印模板（任务码标签等）
运行：cd backend && PYTHONPATH=. python3 scripts/seed_print_templates.py --tenant-code DEMO
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.crud.print_template import create_print_template, get_print_template_by_code, update_print_template
from app.models.tenant import Tenant
from scripts.data.default_print_templates import DEFAULT_PRINT_TEMPLATES


def log(msg: str) -> None:
    print(f"  [PRINT] {msg}")


def seed_for_tenant(db: Session, tenant_id: int) -> int:
    created = 0
    for code, name, template_type, content in DEFAULT_PRINT_TEMPLATES:
        existing = get_print_template_by_code(db, tenant_id, code)
        if existing:
            if not existing.is_active or existing.content != content:
                update_print_template(
                    db, existing, name=name, template_type=template_type, content=content, is_active=True
                )
                log(f"更新模板: {code}")
            continue
        create_print_template(
            db, tenant_id=tenant_id, code=code, name=name, template_type=template_type, content=content, is_active=True
        )
        created += 1
        log(f"创建模板: {code} ({name})")
    return created


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-code", default="DEMO")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.code == args.tenant_code))
        if not tenant:
            raise SystemExit(f"租户不存在: {args.tenant_code}")
        n = seed_for_tenant(db, tenant.id)
        db.commit()
        log(f"完成，新建 {n} 条（租户 {tenant.code}）")
    except Exception as e:
        db.rollback()
        log(f"失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
