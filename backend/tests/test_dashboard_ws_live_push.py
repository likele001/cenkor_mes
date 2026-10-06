# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""P1.3 端到端：业务接口 commit 之后，已连接的大屏真的收到 refresh。

test_dashboard_ws_refresh.py 分别验证了监听器和 hub；这里把
「真接口 + 真 WebSocket 连接 + 跨线程投递」串起来，证明
ws_hub.broadcast 不再是零生产者的死代码。

用临时文件 SQLite（不是 :memory:）：必须让端点真的 commit，
共享连接上的「外部事务 + 每测试回滚」那套 fixture 不会产生真正的
after_commit，测不到这条链路。

收消息用带超时的线程包起来：链路断掉时报错，而不是把 pytest 挂在
receive_json 上。
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ws import dashboard as ws_module
from app.core.deps import get_current_user, get_db
from app.models.base import Base
from app.models.customer import Customer
from app.models.permission import Permission
from app.models.product import Product
from app.models.role import Role
from app.models.sku import Sku
from app.models.user import User, user_roles

# crm_adapter 的表不在 app/models 包里，需显式导入才会进 Base.metadata
from app.integration.crm_adapter import models as _crm_models  # noqa: F401

ADMIN_ORDERS = "/api/admin/production/orders"


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    path = tmp_path_factory.mktemp("ws_push") / "dashboard_ws.db"
    e = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture(scope="module")
def seed(engine):
    db = sessionmaker(bind=engine)()
    try:
        perm = Permission(code="order.create", name="order.create")
        role = Role(code="screen_probe", name="大屏探针", permissions=[perm])
        user = User(
            username="screen-probe",
            password_hash="$2b$12$fakehashscreen",
            full_name="大屏",
            is_active=True,
            roles=[role],
        )
        customer = Customer(code="C-WS-PROBE", name="探针客户")
        product = Product(code="P-WS-PROBE", name="探针产品")
        db.add_all([perm, role, user, customer, product])
        db.flush()
        sku = Sku(product_id=product.id, code="S-WS-PROBE", name="探针型号", is_active=True)
        db.add(sku)
        db.commit()
        return {"user_id": user.id, "customer_id": customer.id, "sku_id": sku.id}
    finally:
        db.close()


@pytest.fixture
def live_client(engine, seed, monkeypatch):
    """不用 `with TestClient(...)`，避免触发 startup 的 create_all（那会碰真实 MySQL）。"""
    from app.main import app

    maker = sessionmaker(bind=engine)

    def _override_db():
        db = maker()
        try:
            yield db
        finally:
            db.close()

    user = maker().get(User, seed["user_id"])

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    # WS 握手的 _user_from_token 自己开 SessionLocal（真 MySQL），这里换成探针用户
    monkeypatch.setattr(ws_module, "_user_from_token", lambda token: user)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _recv(ws, seconds: float = 5.0) -> dict:
    box: list = []

    def _read() -> None:
        try:
            box.append(ws.receive_json())
        except Exception as e:  # noqa: BLE001
            box.append(e)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(seconds)
    if not box:
        pytest.fail(f"{seconds}s 内没收到任何 WS 消息：看板推送又断了")
    if isinstance(box[0], Exception):
        pytest.fail(f"接收 WS 消息失败：{box[0]!r}")
    return box[0]


def test_screen_socket_registers_and_releases(live_client):
    """连接计数要对得上：断开的客户端要被摘掉，否则广播会对着死 socket 反复失败。"""
    with live_client.websocket_connect("/api/ws/dashboard?token=fake") as ws:
        assert ws_module.dashboard_ws_hub.client_count == 1
    assert ws_module.dashboard_ws_hub.client_count == 0


def test_order_create_reaches_connected_screen(live_client, seed):
    with live_client.websocket_connect("/api/ws/dashboard?token=fake") as ws:
        resp = live_client.post(
            ADMIN_ORDERS,
            json={
                "customer_id": seed["customer_id"],
                "code": "SO-WS-LIVE-1",
                "due_date": "2026-10-20",
                "items": [{"line_no": 1, "sku_id": seed["sku_id"], "qty": 5}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 200, resp.json()

        msg = _recv(ws)
        assert msg["type"] == "refresh"
        assert "orders" in msg["changed"]


def test_disconnected_screen_gets_nothing(live_client, seed):
    """没人订阅时不该白白跑一遍序列化。"""
    resp = live_client.post(
        ADMIN_ORDERS,
        json={
            "customer_id": seed["customer_id"],
            "code": "SO-WS-LIVE-2",
            "due_date": "2026-10-21",
            "items": [{"line_no": 1, "sku_id": seed["sku_id"], "qty": 3}],
        },
    )
    assert resp.json()["code"] == 200, resp.json()
    assert ws_module.dashboard_ws_hub.client_count == 0
