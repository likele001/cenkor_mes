# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""系统版本口径回归：同日连发多版本不能显示成旧版本。

回归背景：2026-11-06 一天内连发 v2.2.6~v2.2.10，五条 release_date 相同，
get_latest_version() 只按日期倒序，MySQL 返回 id 最小的 v2.2.6，
导致「系统版本」页显示旧版本号，重启也不会变。
"""
from datetime import date

import app.crud.system_version as sv
from app.crud.system_version import (
    create_version,
    get_current_version,
    get_latest_version,
    list_versions,
    read_local_version,
)


def _seed(session, items):
    for ver, day in items:
        create_version(session, ver, date.fromisoformat(day), f"desc {ver}")
    session.flush()


def test_same_release_date_returns_newest_by_id(session):
    _seed(session, [
        ("v2.2.6", "2026-11-06"),
        ("v2.2.7", "2026-11-06"),
        ("v2.2.8", "2026-11-06"),
        ("v2.2.9", "2026-11-06"),
        ("v2.2.10", "2026-11-06"),
    ])
    assert get_latest_version(session).version == "v2.2.10"


def test_release_date_still_dominates_id(session):
    """id 更大但发布日期更早，不应被当成最新版本。"""
    _seed(session, [
        ("v2.2.10", "2026-11-06"),
        ("v9.9.9", "2026-11-05"),
    ])
    assert get_latest_version(session).version == "v2.2.10"


def test_history_same_date_newest_first(session):
    _seed(session, [
        ("v2.2.6", "2026-11-06"),
        ("v2.2.9", "2026-11-06"),
        ("v2.2.10", "2026-11-06"),
        ("v2.2.1", "2026-11-05"),
    ])
    assert [r.version for r in list_versions(session)] == [
        "v2.2.10", "v2.2.9", "v2.2.6", "v2.2.1",
    ]


def test_history_pagination_is_stable(session):
    _seed(session, [
        ("v2.2.6", "2026-11-06"),
        ("v2.2.9", "2026-11-06"),
        ("v2.2.10", "2026-11-06"),
    ])
    assert [r.version for r in list_versions(session, offset=1, limit=1)] == ["v2.2.9"]


def test_current_version_uses_version_file(session, tmp_path, monkeypatch):
    """口径：当前系统版本 = VERSION 文件，而非开发日志中日期最新的一条。"""
    _seed(session, [
        ("v2.2.6", "2026-11-06"),
        ("v2.2.10", "2026-11-06"),
    ])
    f = tmp_path / "VERSION"
    f.write_text("v2.2.10\n", encoding="utf-8")
    monkeypatch.setattr(sv, "VERSION_FILE", f)
    assert read_local_version() == "v2.2.10"
    assert get_current_version(session).version == "v2.2.10"


def test_current_version_falls_back_when_not_in_changelog(session, tmp_path, monkeypatch):
    _seed(session, [("v2.2.6", "2026-11-06"), ("v2.2.10", "2026-11-06")])
    f = tmp_path / "VERSION"
    f.write_text("v9.9.9", encoding="utf-8")  # 表里没有这条
    monkeypatch.setattr(sv, "VERSION_FILE", f)
    assert get_current_version(session).version == "v2.2.10"


def test_current_version_falls_back_when_file_missing(session, tmp_path, monkeypatch):
    _seed(session, [("v2.2.6", "2026-11-06"), ("v2.2.10", "2026-11-06")])
    monkeypatch.setattr(sv, "VERSION_FILE", tmp_path / "not-exist")
    assert read_local_version() == ""
    assert get_current_version(session).version == "v2.2.10"


def test_current_version_on_empty_table_returns_none(session, tmp_path, monkeypatch):
    f = tmp_path / "VERSION"
    f.write_text("v2.2.10", encoding="utf-8")
    monkeypatch.setattr(sv, "VERSION_FILE", f)
    assert get_current_version(session) is None
