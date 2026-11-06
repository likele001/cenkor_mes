# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""报价单金额核算回归测试。

守的是一类「表头金额与明细行对不上」的缺陷（2026-11-06 生产实测）：

1. 税额曾按**单据级 tax_rate 一刀切**，行上的 tax_rate 只落在行里不参与合计。
   混合税率单据（如软件 13% + 实施服务 6%）含税总额会偏高。
2. 算净额时漏掉了**行折扣**：行 amount 已扣行折扣，表头 subtotal 却按折前累加，
   两者永远对不上。

现口径（`_compute_quotation_amounts` 唯一实现，创建与更新共用）：
    小计     = Σ 数量 × 单价                        （折前，表头展示）
    行净额   = 数量 × 单价 × (1 − 行折扣率)
    单据折扣 = (小计 − Σ行折扣额) × 单据折扣率
    折后净额 = 小计 − Σ行折扣额 − 单据折扣
    行税额   = 行净额 × (1 − 单据折扣率) × 行税率（行税率<=0 回退单据税率）
    含税合计 = 折后净额 + Σ行税额
"""
from decimal import Decimal

import pytest

from app.crud.crm import _compute_quotation_amounts, _dec

# SQLite 下 BigInteger 主键不自增（MySQL 有 AUTO_INCREMENT），
# 建表前把 BigInteger 映射成 INTEGER，否则插入即 NOT NULL constraint failed: id
from sqlalchemy import BigInteger  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):  # noqa: ANN001, ARG001
    return "INTEGER"


# ── 纯函数口径 ──

def test_line_tax_rates_participate_in_total():
    """混合税率：软件 13% / 服务 6%，税额必须逐行按各自税率算。"""
    items = [
        {"quantity": 1, "unit_price": 480000, "tax_rate": Decimal("0.13")},
        {"quantity": 1, "unit_price": 150000, "tax_rate": Decimal("0.13")},
        {"quantity": 60, "unit_price": 2500, "tax_rate": Decimal("0.06")},
    ]
    subtotal, tax, total = _compute_quotation_amounts(
        items, Decimal("0.05"), Decimal("0.13")
    )
    assert subtotal == Decimal("780000")
    # 480000×0.95×13% + 150000×0.95×13% + 150000×0.95×6%
    assert tax == Decimal("86355")
    assert total == Decimal("827355"), "旧算法按 13% 一刀切会得到 837330，多算 9975"


def test_missing_line_tax_falls_back_to_header_rate():
    """行税率没填时回退单据级税率，保证「只填单据税率」的旧用法结果不变。"""
    items = [{"quantity": 2, "unit_price": 100}]
    subtotal, tax, total = _compute_quotation_amounts(
        items, Decimal("0"), Decimal("0.13")
    )
    assert subtotal == Decimal("200")
    assert tax == Decimal("26")
    assert total == Decimal("226")


def test_all_zero_line_tax_matches_legacy_behaviour():
    """全部行税率为 0 且无行折扣时，结果必须与旧算法逐分一致（向后兼容）。"""
    items = [
        {"quantity": 3, "unit_price": 1000, "tax_rate": Decimal("0")},
        {"quantity": 1, "unit_price": 500},
    ]
    subtotal, tax, total = _compute_quotation_amounts(
        items, Decimal("0.10"), Decimal("0.13")
    )
    net = Decimal("3500") * Decimal("0.90")
    assert subtotal == Decimal("3500")
    assert tax == net * Decimal("0.13")
    assert total == net + net * Decimal("0.13")


def test_line_discount_reduces_net_before_tax():
    """行折扣必须先进净额再计税；小计仍保持折前（表头展示口径）。"""
    items = [
        {
            "quantity": 1,
            "unit_price": 1000,
            "discount_rate": Decimal("0.10"),
            "tax_rate": Decimal("0.13"),
        }
    ]
    subtotal, tax, total = _compute_quotation_amounts(items, Decimal("0"), Decimal("0.13"))
    assert subtotal == Decimal("1000"), "小计是折前合计"
    assert tax == Decimal("117"), "税额按折后 900 计"
    assert total == Decimal("1017"), "合计必须等于 900 + 117，而不是 1000 + 117"


def test_header_discount_applies_before_tax():
    items = [{"quantity": 1, "unit_price": 1000, "tax_rate": Decimal("0.13")}]
    subtotal, tax, total = _compute_quotation_amounts(
        items, Decimal("0.10"), Decimal("0.13")
    )
    assert subtotal == Decimal("1000")
    assert tax == Decimal("117")
    assert total == Decimal("1017")


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, Decimal("0")),
        ("", Decimal("0")),
        ("abc", Decimal("0")),
        ("12.5", Decimal("12.5")),
        (13.5, Decimal("13.5")),
        (Decimal("0.06"), Decimal("0.06")),
    ],
)
def test_dec_is_tolerant(raw, expected):
    assert _dec(raw) == expected


# ── 落库路径（创建 / 更新 必须共用同一口径）──

@pytest.fixture
def tenant(session):
    from app.models.tenant import Tenant

    t = session.get(Tenant, 1)
    if t is None:
        t = Tenant(id=1, code="T1", name="默认工厂", status="active")
        session.add(t)
        session.flush()
    return t


def test_create_quotation_persists_line_based_tax(session, tenant):
    from app.crud.crm import create_quotation_with_items

    q = create_quotation_with_items(
        session,
        tenant_id=1,
        customer_id=56,
        title="混合税率落库",
        items_data=[
            {"product_name": "MES", "quantity": 1, "unit_price": 480000, "tax_rate": 0.13},
            {"product_name": "实施", "quantity": 60, "unit_price": 2500, "tax_rate": 0.06},
        ],
        tax_rate=Decimal("0.13"),
        discount_rate=Decimal("0.05"),
    )
    session.flush()
    assert q.subtotal == Decimal("630000")
    assert q.tax_amount == Decimal("67830")   # 480000×.95×13% + 150000×.95×6%
    assert q.total_amount == Decimal("666330")


def test_update_quotation_recomputes_with_line_tax(session, tenant):
    from app.crud.crm import create_quotation_with_items, update_quotation

    q = create_quotation_with_items(
        session,
        tenant_id=1,
        customer_id=56,
        title="更新重算",
        items_data=[{"product_name": "A", "quantity": 1, "unit_price": 1000, "tax_rate": 0.13}],
        tax_rate=Decimal("0.13"),
        discount_rate=Decimal("0.05"),
    )
    session.flush()

    update_quotation(
        session,
        q,
        items_data=[{"product_name": "B", "quantity": 1, "unit_price": 1000, "tax_rate": 0.06}],
    )
    session.flush()
    assert q.subtotal == Decimal("1000")
    assert q.tax_amount == Decimal("57"), "更新后必须按新行的 6% 重算，而不是沿用旧的 13%"
    assert q.total_amount == Decimal("1007")
