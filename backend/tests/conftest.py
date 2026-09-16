# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""pytest fixtures: 使用 SQLite 内存数据库进行单元测试

本次按 cenkormes 真实 schema 对齐：核心业务表（Role/Department/User/Product/Sku/
Process/ProcessPrice/Customer/Order/...）均不含 tenant_id，故 fixtures 不再传入
tenant_id，仅 Tenant 表自身保留多租户字段。
"""
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# 测试环境跳过 bcrypt（版本兼容问题）
def _fake_hash(pw: str) -> str:
    return f"$2b$12$fakehash{pw}"
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import User, user_roles
from app.models.role import Role, role_permissions
from app.models.permission import Permission
from app.models.department import Department
from app.models.product import Product
from app.models.sku import Sku
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.work_order import WorkOrder
from app.models.task import Task
from app.models.report import Report, ReportAudit
from app.models.salary import SalaryItem
from app.models.salary_allowance import SalaryAllowance
try:
    from app.models.ai import AiAlertEvent, AiConversation, AiMessage, PlatformAiModel, PlatformAiProfile
except ImportError:
    # cenkormes 未内置 AI 模型表（app.models.ai 不存在），AI 相关测试在含该模块的环境单独运行
    AiAlertEvent = AiConversation = AiMessage = PlatformAiModel = PlatformAiProfile = None

# --- 全量注册模型元数据，避免 create_all 时外键引用缺表 ---
import importlib
import pkgutil
import app.models as _models_full
for _m in pkgutil.iter_modules(_models_full.__path__):
    try:
        importlib.import_module(f"app.models.{_m.name}")
    except Exception as _e:  # noqa: BLE001 - 跳过缺依赖的历史模型模块
        print(f"[conftest] skip model {_m.name}: {_e}")


@pytest.fixture(scope="session")
def engine():
    """全局 SQLite 内存引擎"""
    e = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(e, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """每次测试一个独立事务，测试结束回滚"""
    conn = engine.connect()
    trans = conn.begin()
    SessionLocal = sessionmaker(bind=conn)
    db = SessionLocal()
    yield db
    db.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def tenant(session: Session) -> Tenant:
    t = Tenant(code="TEST", name="测试工厂", status="active")
    session.add(t)
    session.flush()
    return t


@pytest.fixture
def admin_role(session: Session) -> Role:
    r = Role(code="admin", name="管理员")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def employee_role(session: Session) -> Role:
    r = Role(code="employee", name="员工")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def test_user(admin_role: Role, session: Session) -> User:
    u = User(
        username="admin",
        password_hash=_fake_hash("admin123"),
        full_name="管理员",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=admin_role.id))
    session.flush()
    return u


@pytest.fixture
def department(session: Session) -> Department:
    d = Department(code="D01", name="生产部", is_active=True)
    session.add(d)
    session.flush()
    return d


@pytest.fixture
def product(session: Session) -> Product:
    p = Product(code="P001", name="测试产品", category="电子", unit="个", is_active=True)
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def sku(product: Product, session: Session) -> Sku:
    s = Sku(product_id=product.id, code="SKU001", name="测试型号A", color="红色", material="塑料", spec="100x50", is_active=True)
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def process(session: Session) -> Process:
    p = Process(code="OP01", name="下料", workshop="金工车间", std_minutes=10, is_active=True)
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def customer(session: Session) -> Customer:
    c = Customer(code="C001", name="测试客户", contact_name="张三", contact_phone="13800138000", is_active=True)
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def process_route(product: Product, process: Process, session: Session) -> ProcessRoute:
    """工艺路线（按产品）"""
    route = ProcessRoute(product_id=product.id, name="默认路线", is_active=True, is_default=True)
    session.add(route)
    session.flush()
    step = ProcessRouteStep(route_id=route.id, process_id=process.id, seq=1)
    session.add(step)
    session.flush()
    return route


@pytest.fixture
def process_price(sku: Sku, process: Process, session: Session) -> ProcessPrice:
    pp = ProcessPrice(sku_id=sku.id, process_id=process.id, unit_price="1.50", is_active=True)
    session.add(pp)
    session.flush()
    return pp


# ── 核心闭环 fixtures ──

@pytest.fixture
def order_item(session: Session, customer: Customer, sku: Sku) -> tuple:
    """订单 + 订单行"""
    from app.models.order import Order, OrderItem
    order = Order(customer_id=customer.id, code="SO-TEST", status="confirmed", amount=0, cost_amount=0)
    session.add(order)
    session.flush()
    item = OrderItem(order_id=order.id, line_no=1, sku_id=sku.id, qty=100, unit_price=1.5, subtotal=150.0)
    session.add(item)
    session.flush()
    return order, item


@pytest.fixture
def work_order(session: Session, order_item: tuple, sku: Sku, product: Product) -> "WorkOrder":
    """工单"""
    from app.models.work_order import WorkOrder
    order, item = order_item
    wo = WorkOrder(
        order_id=order.id, order_item_id=item.id, product_id=product.id, sku_id=sku.id,
        qty=100, status="open", standard_hours=0, actual_hours=0,
    )
    session.add(wo)
    session.flush()
    return wo


@pytest.fixture
def task(session: Session, work_order: "WorkOrder", process: Process) -> "Task":
    """工序任务"""
    from app.models.task import Task
    t = Task(
        work_order_id=work_order.id, process_id=process.id, seq=1,
        task_code="T-CORE-001", planned_qty=100, status="pending",
    )
    session.add(t)
    session.flush()
    return t


@pytest.fixture
def assignment(session: Session, task: "Task", test_user: User) -> "TaskAssignment":
    """派工记录"""
    from app.models.task_assignment import TaskAssignment
    a = TaskAssignment(task_id=task.id, user_id=test_user.id, assigned_qty=100, assigned_by=test_user.id)
    session.add(a)
    session.flush()
    return a