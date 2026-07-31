from scripts.import_scanwork_ref import _sku_code


def test_sku_code_legacy_negative_suffix_uses_name():
    """老系统 model_code=-2 不应生成 SW-M9--2。"""
    assert _sku_code(9, "-2", "3+F") == "SW-M9-3+F"
    assert _sku_code(8, "-3", "3+踏") == "SW-M8-3+踏"


def test_sku_code_real_model_code_kept():
    assert _sku_code(19, "01", "4人") == "SW-M19-01"
    assert _sku_code(46, "9", "3+1") == "SW-M46-9"


def test_sku_code_placeholder_uses_name():
    assert _sku_code(12, "", "3人") == "SW-M12-3人"
    assert _sku_code(6, "-", "3+F") == "SW-M6-3+F"
