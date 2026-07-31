"""主数据编码自动生成"""

from sqlalchemy.orm import Session

from app.crud.product import get_product_by_code
from app.crud.supplier import create_supplier, get_supplier_by_code
from app.services.code_generator import BizType, resolve_code


def test_resolve_code_supplier_auto(tenant, session: Session):
    code = resolve_code(
        session,
        tenant_id=tenant.id,
        biz_type=BizType.SUPPLIER,
        code=None,
        exists=lambda c: get_supplier_by_code(session, tenant.id, c) is not None,
    )
    assert code.startswith("SUP")
    create_supplier(session, tenant_id=tenant.id, code=code, name="自动供应商", contact_name=None, phone=None, address=None, remark=None, is_active=True)
    session.flush()
    assert get_supplier_by_code(session, tenant.id, code) is not None


def test_resolve_code_product_auto(tenant, session: Session):
    code = resolve_code(
        session,
        tenant_id=tenant.id,
        biz_type=BizType.PRODUCT,
        code=None,
        exists=lambda c: get_product_by_code(session, tenant.id, c) is not None,
    )
    assert code.startswith("PRD")


def test_resolve_code_manual_syncs_sequence(tenant, session: Session):
    """预览号当手工提交时，序号应推进，下次自动生成不为 001。"""
    from app.services.code_generator import preview_next_code

    preview = preview_next_code(session, tenant.id, BizType.ORDER)
    assert preview.endswith("0001")

    used: list[str] = []

    def exists(c: str) -> bool:
        return c in used

    c1 = resolve_code(
        session,
        tenant_id=tenant.id,
        biz_type=BizType.ORDER,
        code=preview,
        exists=exists,
    )
    used.append(c1)
    session.flush()

    c2 = resolve_code(
        session,
        tenant_id=tenant.id,
        biz_type=BizType.ORDER,
        code=None,
        exists=exists,
    )
    assert c2.endswith("0002")
    assert c1 != c2
