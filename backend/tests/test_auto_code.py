# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""主数据编码自动生成（单租户接口）"""
from sqlalchemy.orm import Session

from app.crud.product import get_product_by_code
from app.crud.supplier import create_supplier, get_supplier_by_code
from app.services.code_generator import BizType, resolve_code


def test_resolve_code_supplier_auto(session: Session):
    code = resolve_code(
        session,
        biz_type=BizType.SUPPLIER,
        code=None,
        exists=lambda c: get_supplier_by_code(session, c) is not None,
    )
    assert code.startswith("SUP")
    create_supplier(session, code, "自动供应商", None, None, None, None, True)
    session.flush()
    assert get_supplier_by_code(session, code) is not None


def test_resolve_code_product_auto(session: Session):
    code = resolve_code(
        session,
        biz_type=BizType.PRODUCT,
        code=None,
        exists=lambda c: get_product_by_code(session, c) is not None,
    )
    assert code.startswith("PRD")


def test_resolve_code_manual_syncs_sequence(session: Session):
    """预览号当手工提交时，序号应推进，下次自动生成不为 001。"""
    from app.services.code_generator import preview_next_code

    preview = preview_next_code(session, BizType.ORDER)
    assert preview.endswith("0001")

    used: list[str] = []

    def exists(c: str) -> bool:
        return c in used

    c1 = resolve_code(
        session,
        biz_type=BizType.ORDER,
        code=preview if preview not in used else None,
        exists=exists,
    )
    used.append(c1)
    session.flush()

    c2 = resolve_code(
        session,
        biz_type=BizType.ORDER,
        code=None,
        exists=exists,
    )
    assert c2.endswith("0002")
    assert c1 != c2