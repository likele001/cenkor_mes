from types import SimpleNamespace

from app.services.code_generator import BizType, _format_code, _RULES


def test_format_daily_code():
    rule = _RULES[BizType.ORDER]
    assert _format_code(rule, "20260520", 1) == "ORD202605200001"
    assert _format_code(rule, "20260520", 12) == "ORD202605200012"
