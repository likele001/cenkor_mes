# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""报工记录（H5 /h5/report-units）契约测试。

第二十二批的两个护栏：

1. ``draft`` 是报工前的占位槽位（sync_unit_slots 按 assigned_qty 预建 1..N），
   报工记录这种「已发生事实」的列表必须能排除它们，否则 100 个空槽位会把
   几条真实记录挤到窗口外，页面看着像「没有记录」。
2. ``exclude_draft`` 必须真的从 HTTP 层传到 CRUD，不能只是签名里加了个参数。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.crud import report_unit as crud  # noqa: E402


def _capture(exclude_draft: bool) -> tuple[str, list]:
    """跑一遍 list_report_units，把生成的 SQL 文本与绑定参数抓出来。"""
    seen: dict[str, object] = {}

    class _Result:
        def all(self):
            return []

    def fake_scalars(stmt):
        compiled = stmt.compile()
        seen["sql"] = str(compiled)
        seen["params"] = list(compiled.params.values())
        return _Result()

    db = MagicMock()
    db.scalars = fake_scalars
    crud.list_report_units(db, user_id=7, exclude_draft=exclude_draft, offset=0, limit=20)
    return seen["sql"], seen["params"]


def test_list_report_units_excludes_draft_slots():
    sql, params = _capture(True)
    assert "report_units.status != " in sql
    # draft 走的是绑定参数，不在 SQL 文本里，必须查参数值
    assert "draft" in params


def test_list_report_units_keeps_draft_by_default():
    # 不传 exclude_draft 时行为必须和以前完全一致：管理端还要看得到待报槽位
    sql, params = _capture(False)
    assert "status != " not in sql
    assert "draft" not in params


def test_h5_report_units_forwards_exclude_draft(monkeypatch):
    from app.api.h5 import report_units as api

    captured: dict[str, object] = {}

    def fake_list(db, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(api, "list_report_units", fake_list)
    monkeypatch.setattr(api, "_ensure_report_read", lambda user: None)

    user = MagicMock(id=11)
    api.my_report_units_api(status=None, exclude_draft=True, offset=0, limit=20,
                            db=MagicMock(), user=user)
    assert captured["exclude_draft"] is True
    assert captured["user_id"] == 11

    api.my_report_units_api(status=None, exclude_draft=False, offset=0, limit=20,
                            db=MagicMock(), user=user)
    assert captured["exclude_draft"] is False


def test_h5_report_history_page_asks_for_submitted_only():
    page = (BACKEND.parent / "frontend-h5/src/pages/ReportHistoryPage.vue").read_text(encoding="utf-8")
    for marker in ("exclude_draft: true", "getReportUnitDetail", "加载更多", "审核轨迹"):
        assert marker in page, f"报工记录页缺少: {marker}"
    # 前端不应该再自己按 status 过滤 draft：服务端已经排除，前端过滤会让分页错位
    assert ".filter((x) => x.status !== 'draft')" not in page
