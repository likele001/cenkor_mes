"""BOM API 测试"""

from app.api.admin.master import boms as boms_api
from app.crud.material import create_material
from app.crud.material_bom import BOM_SCOPE_SKU, create_bom, list_boms
from app.crud.product import create_product
from app.crud.sku import create_sku


def test_list_boms_and_out(session, tenant, test_user):
    product = create_product(
        session,
        tenant_id=tenant.id,
        code="P1",
        name="沙发",
        category=None,
        unit="件",
        description=None,
        is_active=True,
    )
    session.flush()
    sku = create_sku(
        session,
        tenant_id=tenant.id,
        product_id=product.id,
        code="S1",
        name="三人位",
        color=None,
        material=None,
        spec=None,
        remark=None,
        is_active=True,
    )
    mat = create_material(
        session,
        tenant_id=tenant.id,
        code="M1",
        name="布料",
        unit="米",
        spec=None,
        remark=None,
        supplier_id=None,
        is_active=True,
    )
    session.flush()
    create_bom(
        session,
        tenant_id=tenant.id,
        scope=BOM_SCOPE_SKU,
        sku_id=sku.id,
        product_id=product.id,
        name=None,
        version=1,
        remark=None,
        is_default=False,
        created_by=test_user.id,
        items=[(mat.id, 2, None)],
    )
    session.commit()

    items = list_boms(session, tenant_id=tenant.id)
    assert len(items) >= 1
    out = boms_api._out(items[0])
    assert out["scope"] == BOM_SCOPE_SKU
    assert out["items"][0]["material_code"]
