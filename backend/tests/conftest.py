"""pytest fixtures: 使用 SQLite 内存数据库进行单元测试"""

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
from app.models.ai import AiAlertEvent, AiConversation, AiMessage, PlatformAiModel, PlatformAiProfile


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
    t = Tenant(code="TEST", name="测试工厂")
    session.add(t)
    session.flush()
    return t


@pytest.fixture
def admin_role(tenant: Tenant, session: Session) -> Role:
    r = Role(tenant_id=tenant.id, code="admin", name="管理员")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def employee_role(tenant: Tenant, session: Session) -> Role:
    r = Role(tenant_id=tenant.id, code="employee", name="员工")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def test_user(tenant: Tenant, admin_role: Role, session: Session) -> User:
    u = User(
        tenant_id=tenant.id,
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
def department(tenant: Tenant, session: Session) -> Department:
    d = Department(tenant_id=tenant.id, code="D01", name="生产部", is_active=True)
    session.add(d)
    session.flush()
    return d


@pytest.fixture
def product(tenant: Tenant, session: Session) -> Product:
    p = Product(tenant_id=tenant.id, code="P001", name="测试产品", category="电子", unit="个", is_active=True)
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def sku(product: Product, tenant: Tenant, session: Session) -> Sku:
    s = Sku(tenant_id=tenant.id, product_id=product.id, code="SKU001", name="测试型号A", color="红色", material="塑料", spec="100x50", is_active=True)
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def process(tenant: Tenant, session: Session) -> Process:
    p = Process(tenant_id=tenant.id, code="OP01", name="下料", workshop="金工车间", std_minutes=10, is_active=True)
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def customer(tenant: Tenant, session: Session) -> Customer:
    c = Customer(tenant_id=tenant.id, code="C001", name="测试客户", contact_name="张三", contact_phone="13800138000", is_active=True)
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def process_route(tenant: Tenant, product: Product, process: Process, session: Session) -> ProcessRoute:
    """工艺路线（按产品）"""
    route = ProcessRoute(tenant_id=tenant.id, product_id=product.id, name="默认路线", is_active=True, is_default=True)
    session.add(route)
    session.flush()
    step = ProcessRouteStep(tenant_id=tenant.id, route_id=route.id, process_id=process.id, seq=1)
    session.add(step)
    session.flush()
    return route


@pytest.fixture
def process_price(sku: Sku, process: Process, tenant: Tenant, session: Session) -> ProcessPrice:
    pp = ProcessPrice(tenant_id=tenant.id, sku_id=sku.id, process_id=process.id, unit_price="1.50", is_active=True)
    session.add(pp)
    session.flush()
    return pp
