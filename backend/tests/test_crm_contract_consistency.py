# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""CRM 端点契约回归测试。

守的是这样一类缺陷（2026-11-06 实测存在）：
API 层按「想象中的 crud」写函数名与参数，与 `app/crud/crm.py` 的真实实现错位，
导致大量端点直接走 `_not_implemented()` 返回 501，或参数不匹配抛 TypeError 变 500，
而前端 `api/customers.ts` / `api/production.ts` 明确在调这些接口。

断言口径（与本项目全局异常处理器一致）：
  HTTP 恒 200，业务码在 body["code"]；成功为 200。
  这里额外断言 code 不落在 {500, 501}，防止「状态码好看、业务挂了」。
"""
import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.models.permission import Permission
from app.models.role import role_permissions
from app.models.user import User, user_roles

BASE = "/api/admin/production/crm"
BAD_CODES = {500, 501}

# SQLite 下 BigInteger 主键不会自增（MySQL 有 AUTO_INCREMENT），
# 建表前把 BigInteger 映射成 INTEGER，否则插入即 NOT NULL constraint failed。
from sqlalchemy import BigInteger  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):  # noqa: ANN001, ARG001
    return "INTEGER"



# ── 脚手架（与 test_api_integration_core_flow 同构：StaticPool + 不触发 startup） ──

@pytest.fixture(scope="session")
def engine():
    from app.models.base import Base

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def api(session):
    from app.main import app

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def single_tenant(session):
    """独立版是单租户：User.tenant_id 硬编码返回 1，这里确保 tenants 表有 id=1。"""
    from app.models.tenant import Tenant

    t = session.get(Tenant, 1)
    if t is None:
        t = Tenant(id=1, code="T1", name="默认工厂", status="active")
        session.add(t)
        session.flush()
    return t


@pytest.fixture
def crm_user(session, single_tenant, admin_role):
    """持有 customer.manage 的真实用户，走完整 RBAC 查询链路。

    不传 tenant_id：User.tenant_id 是只读 property，单用户版恒为 1。
    """
    u = User(
        username="crm-admin",
        password_hash="x",
        full_name="CRM管理员",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=admin_role.id))
    p = Permission(code="customer.manage", name="customer.manage")
    session.add(p)
    session.flush()
    session.execute(
        role_permissions.insert().values(role_id=admin_role.id, permission_id=p.id)
    )
    session.flush()
    return u


@pytest.fixture
def crm_customer(session, single_tenant):
    from app.models.customer import Customer

    # Customer 模型不含 tenant_id（独立版单租户），只传业务字段
    c = Customer(code="C-CRM-1", name="契约测试客户")
    session.add(c)
    session.flush()
    return c


def _expect_ok(resp, step: str) -> dict:
    body = resp.json()
    assert resp.status_code == 200, f"{step}: HTTP {resp.status_code}"
    assert body.get("code") not in BAD_CODES, f"{step}: 业务码 {body.get('code')} -> {body.get('msg') or body}"
    assert body.get("code") == 200, f"{step}: 未成功 {body.get('code')} -> {body.get('msg') or body}"
    return body.get("data") or {}


# ── 报价单闭环：create -> get -> new-version -> send -> reject ──

def test_quotation_flow_no_501_500(api, crm_user, crm_customer):
    h = _auth(crm_user)

    created = _expect_ok(
        api.post(
            f"{BASE}/quotations",
            headers=h,
            json={
                "customer_id": crm_customer.id,
                "title": "契约回归报价",
                "items": [
                    {"product_name": "测试件", "quantity": 2, "unit_price": 100},
                ],
            },
        ),
        "创建报价单",
    )
    qid = created["id"]
    assert qid

    detail = _expect_ok(api.get(f"{BASE}/quotations/{qid}", headers=h), "报价单详情")
    assert isinstance(detail.get("items"), list), "详情必须带回商品行"
    assert len(detail["items"]) == 1

    _expect_ok(api.post(f"{BASE}/quotations/{qid}/new-version", headers=h), "报价单新版本")
    _expect_ok(api.post(f"{BASE}/quotations/{qid}/send", headers=h), "报价单发送")
    # reject 曾传 crud 不存在的 user_id，必 TypeError
    _expect_ok(
        api.post(f"{BASE}/quotations/{qid}/reject", headers=h, json={"reason": "价格偏高"}),
        "报价单驳回",
    )


def test_quotation_create_without_items_returns_business_error(api, crm_user, crm_customer):
    """没有商品行应是业务错误，而不是 ValueError 冒成 500。"""
    body = api.post(
        f"{BASE}/quotations",
        headers=_auth(crm_user),
        json={"customer_id": crm_customer.id, "title": "空行报价", "items": []},
    ).json()
    assert body.get("code") not in BAD_CODES
    assert body.get("code") != 200


# ── 合同闭环：create -> get -> record payment -> renew -> terminate ──

def test_contract_flow_no_501_500(api, crm_user, crm_customer):
    h = _auth(crm_user)

    created = _expect_ok(
        api.post(
            f"{BASE}/contracts",
            headers=h,
            json={
                "customer_id": crm_customer.id,
                "name": "契约回归合同",
                "payment_plans": [
                    {"phase_name": "首款", "amount": 1000, "due_date": "2026-12-01"},
                    {"phase_name": "尾款", "amount": 2000, "due_date": "2027-01-01"},
                ],
            },
        ),
        "创建合同",
    )
    cid = created["id"]

    detail = _expect_ok(api.get(f"{BASE}/contracts/{cid}", headers=h), "合同详情")
    plans = detail.get("payment_plans") or []
    assert len(plans) == 2, "合同详情必须带回付款计划"

    _expect_ok(
        api.post(
            f"{BASE}/contracts/{cid}/payment-plans/{plans[0]['id']}/record",
            headers=h,
            json={"actual_amount": 1000, "actual_date": "2026-12-01"},
        ),
        "登记收款",
    )
    _expect_ok(api.post(f"{BASE}/contracts/{cid}/renew", headers=h, json={}), "合同续签")
    # terminate 的 crud 函数此前根本不存在
    term = _expect_ok(
        api.post(f"{BASE}/contracts/{cid}/terminate", headers=h, json={"reason": "客户取消"}),
        "合同终止",
    )
    assert term.get("status") == "terminated"


def test_record_payment_rejects_plan_of_another_contract(api, crm_user, crm_customer):
    """付款计划不属于该合同时必须拒绝，不能跨合同改账。"""
    h = _auth(crm_user)
    a = _expect_ok(
        api.post(f"{BASE}/contracts", headers=h,
                 json={"customer_id": crm_customer.id, "name": "合同A",
                       "payment_plans": [{"phase_name": "一次性", "amount": 500}]}),
        "建合同A",
    )
    b = _expect_ok(
        api.post(f"{BASE}/contracts", headers=h,
                 json={"customer_id": crm_customer.id, "name": "合同B",
                       "payment_plans": [{"phase_name": "一次性", "amount": 500}]}),
        "建合同B",
    )
    plans_b = _expect_ok(api.get(f"{BASE}/contracts/{b['id']}", headers=h), "读合同B")["payment_plans"]
    body = api.post(
        f"{BASE}/contracts/{a['id']}/payment-plans/{plans_b[0]['id']}/record",
        headers=h,
        json={"actual_amount": 500},
    ).json()
    assert body.get("code") not in BAD_CODES
    assert body.get("code") != 200, "跨合同登记收款应被拒绝"


# ── 线索跟进活动：此前 offset/limit 必 TypeError ──

def test_lead_activity_list_accepts_pagination(api, crm_user):
    h = _auth(crm_user)
    lead = _expect_ok(
        api.post(f"{BASE}/leads", headers=h,
                 json={"contact_name": "张三", "company": "测试客户公司"}),
        "创建线索",
    )
    lid = lead["id"]
    for i in range(3):
        _expect_ok(
            api.post(f"{BASE}/leads/{lid}/activities", headers=h,
                     json={"action_type": "call", "content": f"第{i}次电话"}),
            f"创建跟进{i}",
        )
    data = _expect_ok(
        api.get(f"{BASE}/leads/{lid}/activities", headers=h, params={"offset": 0, "limit": 2}),
        "活动列表分页",
    )
    assert len(data["items"]) == 2, "limit=2 必须生效"


def test_lead_activity_payload_cannot_override_lead_id(api, crm_user):
    """payload 里塞 lead_id/created_by 不应与路径参数/登录用户冲突。"""
    h = _auth(crm_user)
    lid = _expect_ok(
        api.post(f"{BASE}/leads", headers=h, json={"contact_name": "李四"}), "创建线索"
    )["id"]
    _expect_ok(
        api.post(
            f"{BASE}/leads/{lid}/activities",
            headers=h,
            json={"action_type": "visit", "content": "上门", "lead_id": 999999, "created_by": 999999},
        ),
        "带冲突字段创建跟进",
    )
    data = _expect_ok(api.get(f"{BASE}/leads/{lid}/activities", headers=h), "活动列表")
    assert len(data["items"]) == 1
    assert data["items"][0]["lead_id"] == lid, "必须以路径中的 lead_id 为准"


# ── 销售目标与达成看板 ──

def test_sales_target_and_dashboard(api, crm_user):
    h = _auth(crm_user)
    _expect_ok(
        api.post(f"{BASE}/sales-targets", headers=h,
                 json={"period_type": "month", "period_start": "2026-11-01",
                       "period_end": "2026-11-30", "dimension": "company",
                       "metric": "amount", "target_value": 100000}),
        "创建销售目标",
    )
    # dashboard_sales_targets 的 crud 函数此前不存在
    data = _expect_ok(
        api.get(f"{BASE}/dashboard/sales-targets", headers=h, params={"period_type": "month"}),
        "销售目标看板",
    )
    assert "summary" in data and "items" in data
    assert data["summary"]["count"] >= 1


# ── 客户维度列表：get_customer_by_id 原本取错模块 ──

def test_customer_scoped_lists(api, crm_user, crm_customer):
    h = _auth(crm_user)
    _expect_ok(
        api.get(f"{BASE}/customers/{crm_customer.id}/quotations", headers=h), "客户报价列表"
    )
    _expect_ok(
        api.get(f"{BASE}/customers/{crm_customer.id}/contracts", headers=h), "客户合同列表"
    )
    # 跨租户 / 不存在的客户必须 404 业务码，不能 500
    body = api.get(f"{BASE}/customers/999999/contracts", headers=h).json()
    assert body.get("code") not in BAD_CODES
    assert body.get("code") != 200


# ── 市场活动成员与 ROI ──

def test_campaign_members_and_roi(api, crm_user):
    h = _auth(crm_user)
    cid = _expect_ok(
        api.post(f"{BASE}/campaigns", headers=h,
                 json={"name": "契约回归活动", "type": "expo", "budget": 5000}),
        "创建活动",
    )["id"]

    _expect_ok(
        api.post(f"{BASE}/campaigns/{cid}/members", headers=h,
                 json={"members": [{"member_type": "lead", "member_id": 1}]}),
        "加成员",
    )
    members = _expect_ok(api.get(f"{BASE}/campaigns/{cid}/members", headers=h), "成员列表")
    assert isinstance(members.get("items"), list)

    # campaign_calculate_roi 真实函数名此前写成 recalculate_campaign_roi
    _expect_ok(api.post(f"{BASE}/campaigns/{cid}/recalculate-roi", headers=h), "重算 ROI")
    _expect_ok(
        api.delete(f"{BASE}/campaigns/{cid}/members/lead/1", headers=h), "移除成员"
    )


# ── 胜负原因 ──

def test_win_loss_reason_create(api, crm_user):
    _expect_ok(
        api.post(f"{BASE}/win-loss-reasons", headers=_auth(crm_user),
                 json={"type": "win", "category": "price", "code": "W01", "name": "价格优势"}),
        "创建赢单原因",
    )


# ── 空 body：必须是业务参数错误，绝不能 500/501 ──

@pytest.mark.parametrize(
    "path",
    ["/quotations", "/contracts", "/sales-targets", "/leads", "/win-loss-reasons", "/campaigns"],
)
def test_empty_payload_never_returns_500_or_501(api, crm_user, path):
    """缺必填参数应给 400 业务提示。

    crud 侧这些参数没有默认值，若 API 层不前置校验就 TypeError -> 500，
    这正是 `_payload_dict` 修好后暴露出来的下一层问题。
    """
    body = api.post(f"{BASE}{path}", headers=_auth(crm_user), json={}).json()
    assert body.get("code") not in BAD_CODES, f"{path} 空 body 返回 {body.get('code')}: {body}"
    assert body.get("code") != 200, f"{path} 空 body 不应成功"


# ── 静态闸门：防止再次出现「API 取不存在的 crud 函数」 ──

def test_api_only_references_existing_crud_functions():
    """静态比对：API 层通过 getattr(_crm_crud(), "x") 取的函数名必须真实存在。

    这条守着本次缺陷的根因——改名/重构后 API 层引用失配，
    只会在运行时以 501 暴露，静态期就能拦住。
    """
    root = Path(__file__).resolve().parents[1]
    api_path = root / "app/api/admin/production/crm.py"
    crud_path = root / "app/crud/crm.py"

    crud_names = {
        n.name
        for n in ast.parse(crud_path.read_text(encoding="utf-8")).body
        if isinstance(n, ast.FunctionDef)
    }

    referenced: set[str] = set()
    for node in ast.walk(ast.parse(api_path.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "getattr" or len(node.args) < 2:
            continue
        # 只检 _crm_crud() 这一路；_customer_crud() 的函数在 crud/customer.py
        head = node.args[0]
        if not (isinstance(head, ast.Call) and isinstance(head.func, ast.Name)):
            continue
        if head.func.id != "_crm_crud":
            continue
        arg = node.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            referenced.add(arg.value)

    missing = sorted(referenced - crud_names)
    assert not missing, f"API 层引用了 crud 中不存在的函数：{missing}"


# ── 报价单列表的客户名展示（2026-11-06 实测缺陷）──
#
# 后台列表页要展示「客户」名称，但 crm_quotations 核心表只存 customer_id、
# 没有客户名列；_item_to_dict() 按表列取值 → 返回体里 customer_name 键
# 根本不存在 → 该列永远空白。

def test_quotation_list_includes_customer_name(api, crm_user, crm_customer):
    h = _auth(crm_user)
    _expect_ok(
        api.post(
            f"{BASE}/quotations",
            headers=h,
            json={
                "customer_id": crm_customer.id,
                "title": "客户名展示报价",
                "items": [{"product_name": "测试件", "quantity": 1, "unit_price": 100}],
            },
        ),
        "创建报价单",
    )

    data = _expect_ok(api.get(f"{BASE}/quotations", headers=h), "报价单列表")
    rows = data.get("items") or []
    assert rows, "列表必须能查到刚建的报价单"
    row = next(r for r in rows if r.get("customer_id") == crm_customer.id)
    assert row.get("customer_name") == crm_customer.name, "列表必须补出客户名"
    assert row.get("customer_code") == crm_customer.code, "列表必须补出客户编码"


def test_quotation_list_tolerates_missing_customer(api, session, crm_user, single_tenant):
    """客户被删或脏数据时，补名逻辑要降级为「没有名字」，不能整页 500。"""
    from app.models.crm import CrmQuotation

    q = CrmQuotation(
        tenant_id=1,
        code="Q-ORPHAN-1",
        title="孤儿客户报价",
        customer_id=999999,
        status="draft",
        subtotal=0,
        tax_amount=0,
        total_amount=0,
        version=1,
    )
    session.add(q)
    session.flush()

    data = _expect_ok(api.get(f"{BASE}/quotations", headers=_auth(crm_user)), "孤儿报价单列表")
    row = next(r for r in (data.get("items") or []) if r.get("code") == "Q-ORPHAN-1")
    assert row.get("customer_id") == 999999
    assert not row.get("customer_name"), "查不到客户时不应编造客户名"


# ── 报价单更新：带 items 要能重算金额（2026-11-06 补）──
#
# 旧实现是 upd_fn(db, q, **data) 直接把前端 payload 展开：
# 前端若用 items 命名，与 crud 的 items_data 参数名不匹配 → TypeError → 500，
# 于是也无法通过接口触发金额重算。现与创建接口对齐（兼容 items / items_data，
# 并按注解把 delivery_date 的 ISO 字符串转成 date）。

def test_quotation_update_accepts_items_and_recomputes(api, crm_user, crm_customer):
    h = _auth(crm_user)
    created = _expect_ok(
        api.post(
            f"{BASE}/quotations",
            headers=h,
            json={
                "customer_id": crm_customer.id,
                "title": "更新重算报价",
                "tax_rate": 0.13,
                "items": [
                    {"product_name": "原始行", "quantity": 1, "unit_price": 1000, "tax_rate": 0.13},
                ],
            },
        ),
        "创建报价单",
    )
    qid = created["id"]

    _expect_ok(
        api.put(
            f"{BASE}/quotations/{qid}",
            headers=h,
            json={
                "items": [
                    {
                        "product_name": "改造行",
                        "quantity": 1,
                        "unit_price": 1000,
                        "tax_rate": 0.06,
                        "delivery_date": "2027-01-01",
                    },
                ]
            },
        ),
        "更新报价单（带 items）",
    )

    detail = _expect_ok(api.get(f"{BASE}/quotations/{qid}", headers=h), "报价单详情")
    assert float(detail.get("tax_amount") or 0) == 60.0, "13% 改 6% 后税额必须重算为 60"
    assert float(detail.get("total_amount") or 0) == 1060.0
