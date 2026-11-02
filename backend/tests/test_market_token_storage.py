# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""实例令牌静态加密：新写入为密文、历史明文读时迁移、解不开时按未绑定处理。"""

from app.api.admin.market.router import (
    INSTANCE_TOKEN_KEY,
    TOKEN_ENC_PREFIX,
    _get_instance_token,
    _get_setting,
    _set_instance_token,
)
from app.models.platform_setting import PlatformSetting


def test_set_encrypts_at_rest(session):
    _set_instance_token(session, "tok-abc-123")
    raw = _get_setting(session, INSTANCE_TOKEN_KEY)
    assert raw.startswith(TOKEN_ENC_PREFIX)
    assert "tok-abc-123" not in raw
    assert _get_instance_token(session) == "tok-abc-123"


def test_legacy_plaintext_migrated_on_read(session):
    session.add(PlatformSetting(key=INSTANCE_TOKEN_KEY, value="legacy-plain-token"))
    session.commit()

    assert _get_instance_token(session) == "legacy-plain-token"

    raw = _get_setting(session, INSTANCE_TOKEN_KEY)
    assert raw.startswith(TOKEN_ENC_PREFIX)
    assert "legacy-plain-token" not in raw
    # 迁移后仍可正常读取
    assert _get_instance_token(session) == "legacy-plain-token"


def test_empty_token_clears_row(session):
    _set_instance_token(session, "t")
    _set_instance_token(session, "")
    assert _get_setting(session, INSTANCE_TOKEN_KEY) == ""


def test_decrypt_failure_treated_as_unbound(session, monkeypatch):
    _set_instance_token(session, "tok")
    import app.storage.crypto as crypto

    def boom(_value):
        raise ValueError("bad key")

    monkeypatch.setattr(crypto, "decrypt", boom)
    assert _get_instance_token(session) == ""
