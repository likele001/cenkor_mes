from app.services.display_label import product_display_name, sku_display_name


def test_product_display_uses_name_not_trivial_spec():
    assert product_display_name("30035", "规格:1") == "30035"
    assert product_display_name("30012", "规格:1") == "30012"


def test_product_display_with_meaningful_spec():
    assert product_display_name("30013", "颜色:黑色；规格:3+踏  3人") == "30013 · 3+踏  3人 · 黑色"
    assert product_display_name("30013", "颜色:3+踏  3人；规格:1") == "30013 · 3+踏  3人"


def test_product_display_c_series():
    assert product_display_name("C-01", "颜色:C系列；规格:1") == "C-01 · C系列"


def test_product_display_plain_description():
    assert product_display_name("30013", "真皮三人沙发") == "30013 · 真皮三人沙发"
    assert product_display_name("30013", "30013") == "30013"


def test_sku_display_name():
    assert sku_display_name("3人+妃", "SW-M79-10") == "3人+妃"
