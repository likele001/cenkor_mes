# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from app.services.audit_prescreen import run_prescreen


def test_run_prescreen_unit_not_found(session, tenant):
    try:
        run_prescreen(session, tenant.id, 999999)
        assert False
    except ValueError as e:
        assert "不存在" in str(e)
