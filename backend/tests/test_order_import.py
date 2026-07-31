"""订单 Excel 导入测试（页面填订单头 + Excel 明细）"""

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.process_price import list_prices
from app.crud.sku import get_sku_by_id
from app.models.order import Order, OrderItem
from app.models.process_route import ProcessRoute
from app.services.order_import import OrderImportParams, import_single_order_from_excel


def _detail_excel(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["序号", "产品名称", "型号名称", "颜色", "材料", "规格", "数量", "行备注"])
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_single_order_by_names(tenant, customer, product, sku, session: Session):
    raw = _detail_excel(
        [
            [1, product.name, sku.name, sku.color, sku.material, sku.spec, 10, ""],
            [2, product.name, sku.name, sku.color, sku.material, sku.spec, 20, ""],
        ]
    )
    params = OrderImportParams(
        customer_id=customer.id,
        order_name="春季订单",
        due_date=None,
        auto_create_product=False,
        auto_create_sku=False,
    )
    result = import_single_order_from_excel(session, tenant_id=tenant.id, params=params, raw=raw)
    session.flush()
    assert result["orders_created"] == 1
    assert result["lines_success"] == 2
    assert not result["errors"]
    order = session.scalar(select(Order).where(Order.tenant_id == tenant.id, Order.customer_id == customer.id).order_by(Order.id.desc()))
    assert order is not None
    assert "春季订单" in (order.remark or "")
    items = session.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.line_no)).all()
    assert len(items) == 2


def test_import_product_dash_sku_format(tenant, customer, product, sku, session: Session):
    """产品名称列使用「产品-型号」合并写法。"""
    raw = _detail_excel([[1, f"{product.name}-{sku.name}", "", sku.color, sku.material, sku.spec, 5, ""]])
    params = OrderImportParams(customer_id=customer.id, order_name="合并写法单", auto_create_product=False, auto_create_sku=False)
    result = import_single_order_from_excel(session, tenant_id=tenant.id, params=params, raw=raw)
    session.flush()
    assert result["orders_created"] == 1
    assert result["lines_success"] == 1


def test_import_auto_create_product_sku(tenant, customer, process, process_route, session: Session):
    raw = _detail_excel([[1, "导入新产品Y", "导入型号Z", "绿色", "金属", "10x10", 3, ""]])
    params = OrderImportParams(
        customer_id=customer.id,
        order_name="自动建单",
        auto_create_product=True,
        auto_create_sku=True,
        default_unit_price=2.5,
    )
    result = import_single_order_from_excel(session, tenant_id=tenant.id, params=params, raw=raw)
    session.flush()
    assert result["orders_created"] == 1
    assert result["lines_success"] == 1
    assert len(result["warnings"]) >= 1
    order = session.scalar(select(Order).where(Order.tenant_id == tenant.id, Order.remark.like("%自动建单%")))
    assert order is not None
    item = session.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    assert item is not None
    sku_obj = get_sku_by_id(session, tenant_id=tenant.id, sku_id=item.sku_id)
    assert sku_obj is not None
    prices = list_prices(session, tenant_id=tenant.id, sku_id=item.sku_id, limit=100)
    assert len(prices) == 1
    assert float(prices[0].unit_price) == 2.5
    route = session.scalar(
        select(ProcessRoute).where(
            ProcessRoute.tenant_id == tenant.id,
            ProcessRoute.product_id == sku_obj.product_id,
            ProcessRoute.is_default.is_(True),
        )
    )
    assert route is not None


def test_import_fail_without_auto_create(tenant, customer, session: Session):
    raw = _detail_excel([[1, "不存在的产品", "不存在型号", "", "", "", 1, ""]])
    params = OrderImportParams(customer_id=customer.id, order_name="失败单", auto_create_product=False, auto_create_sku=False)
    result = import_single_order_from_excel(session, tenant_id=tenant.id, params=params, raw=raw)
    session.flush()
    assert result["orders_created"] == 0
    assert result["errors"]
