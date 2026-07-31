"""pricing_ai SKU 关联测试"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai.pricing_ai import suggest_price_adjustments


def test_suggest_price_join_includes_sku_id():
    """SQL 应包含 sku_id 关联，避免同工序跨 SKU 污染。"""
    db = MagicMock()
    captured: dict = {}

    def fake_execute(stmt):
        captured["sql"] = str(stmt)
        return type("R", (), {"all": lambda self: []})()

    db.execute = fake_execute
    suggest_price_adjustments(db, tenant_id=1, min_reports=999)
    sql = captured.get("sql", "")
    assert "sku_id" in sql.lower()
    assert "work_orders" in sql.lower()
