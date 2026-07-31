"""批量添加型号及工序工价"""

from sqlalchemy.orm import Session

from app.crud.process_price import get_price_by_sku_process
from app.crud.sku import get_sku_by_code
from app.services.sku_batch import batch_create_skus_with_prices, get_product_route_processes, list_active_sku_names_for_product


def test_batch_create_skus_with_prices(tenant, product, process, process_route, session: Session):
    result = batch_create_skus_with_prices(
        session,
        tenant.id,
        product.id,
        [
            {
                "name": "红色款",
                "code": "SKU-R",
                "color": "红",
                "prices": [{"process_id": process.id, "unit_price": "1.20", "is_active": True}],
            },
            {
                "name": "蓝色款",
                "code": "SKU-B",
                "prices": [{"process_id": process.id, "unit_price": "1.50", "is_active": True}],
            },
        ],
    )
    session.flush()
    assert result["added"] == 2
    assert result["skipped"] == 0
    assert result["prices_created"] == 2

    sku_r = get_sku_by_code(session, tenant.id, "SKU-R")
    assert sku_r is not None
    pp = get_price_by_sku_process(session, tenant.id, sku_r.id, process.id)
    assert pp is not None
    assert float(pp.unit_price) == 1.2


def test_batch_skip_duplicate_name(tenant, product, sku, process, process_route, session: Session):
    result = batch_create_skus_with_prices(
        session,
        tenant.id,
        product.id,
        [
            {"name": sku.name, "code": "SKU-NEW", "prices": []},
            {"name": "全新型号", "code": "SKU-NEW2", "prices": [{"process_id": process.id, "unit_price": "2.00"}]},
        ],
    )
    session.flush()
    assert result["added"] == 1
    assert result["skipped"] == 1
    assert get_sku_by_code(session, tenant.id, "SKU-NEW") is None
    assert get_sku_by_code(session, tenant.id, "SKU-NEW2") is not None


def test_get_product_route_processes(tenant, product, process, process_route, session: Session):
    rows, route_name, source = get_product_route_processes(session, tenant.id, product.id)
    assert source == "default_route"
    assert route_name == "默认路线"
    assert len(rows) == 1
    assert rows[0].id == process.id


def test_list_active_sku_names(tenant, product, sku, session: Session):
    names = list_active_sku_names_for_product(session, tenant.id, product.id)
    assert sku.name in names
