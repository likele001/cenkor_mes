from app.services.captcha import create_captcha, verify_captcha


def test_captcha_verify_once():
    cid, _b64, _exp = create_captcha()
    # 无法从外部得知明文，仅测错误输入
    assert verify_captcha(cid, "XXXX") is False
    assert verify_captcha(cid, None) is False
