"""主数据 CRUD 测试：产品 / SKU / 工序 / 工价"""

from sqlalchemy.orm import Session

from app.crud.product import create_product, get_product_by_code, list_products
from app.crud.sku import create_sku, get_sku_by_code, list_skus
from app.crud.process import create_process
from app.crud.process_price import create_price, get_price_by_sku_process


def test_create_product(tenant, session: Session):
    p = create_product(session, tenant_id=tenant.id, code="P002", name="新产品", category="五金", unit="件", description=None, is_active=True)
    session.flush()
    assert p.id > 0
    assert p.code == "P002"
    assert p.name == "新产品"
    assert p.category == "五金"
    assert p.unit == "件"

    fetched = get_product_by_code(session, tenant_id=tenant.id, code="P002")
    assert fetched is not None
    assert fetched.id == p.id


def test_list_products_tenant_isolation(tenant, product, session: Session):
    items = list_products(session, tenant_id=tenant.id)
    assert product.id in [p.id for p in items]
    assert len(list_products(session, tenant_id=9999)) == 0


def test_create_sku(tenant, product, session: Session):
    s = create_sku(
        session, tenant_id=tenant.id, product_id=product.id,
        code="SKU002", name="蓝色款", color="蓝色", material="金属", spec="200x100", remark="测试", is_active=True,
    )
    session.flush()
    assert s.code == "SKU002"
    assert s.color == "蓝色"
    assert s.material == "金属"
    assert get_sku_by_code(session, tenant_id=tenant.id, code="SKU002") is not None


def test_sku_duplicate_code(tenant, product, session: Session):
    from sqlalchemy.exc import IntegrityError
    import pytest
    create_sku(session, tenant_id=tenant.id, product_id=product.id, code="UNIQUE", name="A",
               color=None, material=None, spec=None, remark=None, is_active=True)
    session.flush()
    with pytest.raises(IntegrityError):
        create_sku(session, tenant_id=tenant.id, product_id=product.id, code="UNIQUE", name="B",
                   color=None, material=None, spec=None, remark=None, is_active=True)
        session.flush()


def test_process_price(tenant, sku, process, session: Session):
    pp = create_price(session, tenant_id=tenant.id, sku_id=sku.id, process_id=process.id, unit_price="2.00", is_active=True)
    session.flush()
    assert float(pp.unit_price) == 2.0
    fetched = get_price_by_sku_process(session, tenant_id=tenant.id, sku_id=sku.id, process_id=process.id)
    assert fetched is not None
    assert float(fetched.unit_price) == 2.0


def test_process_price_not_found(tenant, sku, process, session: Session):
    assert get_price_by_sku_process(session, tenant_id=tenant.id, sku_id=9999, process_id=process.id) is None
