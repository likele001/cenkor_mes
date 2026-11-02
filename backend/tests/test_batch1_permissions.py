# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""附件读取与审批留痕的权限边界。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.admin.approval import records as records_api
from app.api.v1 import files as files_api
from app.crud.approval_record import list_records
from app.models.approval_record import ApprovalRecord
from app.models.attachment import Attachment
from app.models.user import User


def _user(session, username: str, *, superuser: bool = False) -> User:
    u = User(username=username, password_hash="x", full_name=username, is_active=True, is_superuser=superuser)
    session.add(u)
    session.flush()
    return u


def _attachment(session, uploader: User) -> Attachment:
    att = Attachment(
        uploader_id=uploader.id,
        storage_driver="local",
        storage_key="2026/11/demo.txt",
        original_filename="demo.txt",
        content_type="text/plain",
        size=3,
        sha256="0" * 64,
    )
    session.add(att)
    session.flush()
    return att


# ── 附件读取 ─────────────────────────────────────────────────────────


def test_other_user_without_permission_gets_403(session):
    owner = _user(session, "owner")
    other = _user(session, "other")
    att = _attachment(session, owner)

    with pytest.raises(HTTPException) as exc:
        files_api.get_file(attachment_id=att.id, download=False, url=False,
                           db=session, user=other, permission_codes=[])
    assert exc.value.status_code == 403


def test_uploader_can_read_own_file(session, monkeypatch):
    owner = _user(session, "owner")
    att = _attachment(session, owner)
    monkeypatch.setattr(files_api, "get_storage_for",
                        lambda driver, db: SimpleNamespace(driver="oss"))
    monkeypatch.setattr(files_api, "attachment_play_url",
                        lambda a, db=None: "https://cdn.example.com/demo.txt")

    resp = files_api.get_file(attachment_id=att.id, download=False, url=False,
                              db=session, user=owner, permission_codes=[])
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://cdn.example.com/demo.txt"


def test_attachment_view_permission_can_read(session, monkeypatch):
    owner = _user(session, "owner")
    viewer = _user(session, "viewer")
    att = _attachment(session, owner)
    monkeypatch.setattr(files_api, "get_storage_for",
                        lambda driver, db: SimpleNamespace(driver="oss"))
    monkeypatch.setattr(files_api, "attachment_play_url",
                        lambda a, db=None: "https://cdn.example.com/demo.txt")

    resp = files_api.get_file(attachment_id=att.id, download=False, url=False,
                              db=session, user=viewer, permission_codes=["attachment.view"])
    assert resp.status_code == 302


def test_superuser_can_read_any_file(session, monkeypatch):
    owner = _user(session, "owner")
    root = _user(session, "root", superuser=True)
    att = _attachment(session, owner)
    monkeypatch.setattr(files_api, "get_storage_for",
                        lambda driver, db: SimpleNamespace(driver="oss"))
    monkeypatch.setattr(files_api, "attachment_play_url",
                        lambda a, db=None: "https://cdn.example.com/demo.txt")

    resp = files_api.get_file(attachment_id=att.id, download=False, url=False,
                              db=session, user=root, permission_codes=[])
    assert resp.status_code == 302


def test_missing_attachment_returns_404(session):
    user = _user(session, "u1")
    with pytest.raises(HTTPException) as exc:
        files_api.get_file(attachment_id=999999, download=False, url=False,
                           db=session, user=user, permission_codes=["attachment.view"])
    assert exc.value.status_code == 404


def test_reviewer_roles_can_read_others_attachments():
    """班组长/质检需要查看员工上传的报工现场照片与工资条签名。"""
    from app.core.seed import ROLE_PERMISSION_PRESETS

    assert "attachment.view" in ROLE_PERMISSION_PRESETS["leader"]
    assert "attachment.view" in ROLE_PERMISSION_PRESETS["qc"]
    assert "attachment.view" not in ROLE_PERMISSION_PRESETS["employee"]


# ── 审批留痕 ─────────────────────────────────────────────────────────


@pytest.fixture
def records(session):
    session.add_all([
        ApprovalRecord(biz_type="order", biz_id=1, biz_code="SO-1", action="confirm"),
        ApprovalRecord(biz_type="salary_slip", biz_id=2, biz_code="SL-1", action="confirm"),
        ApprovalRecord(biz_type="statement", biz_id=3, biz_code="CS-1", action="pay"),
    ])
    session.flush()
    return session


def _call(session, user, codes, **kwargs):
    params = dict(biz_type=None, biz_id=None, operator_id=None, action=None, offset=0, limit=50)
    params.update(kwargs)
    return records_api.list_records_api(db=session, user=user, permission_codes=codes, **params)


def test_record_list_requires_some_permission(session, records):
    emp = _user(session, "emp")
    with pytest.raises(HTTPException) as exc:
        _call(session, emp, [])
    assert exc.value.status_code == 403


def test_record_list_is_filtered_by_permission(session, records):
    user = _user(session, "salary_user")
    data = _call(session, user, ["salary.view"], limit=50)
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["biz_type"] == "salary_slip"


def test_record_list_rejects_unrelated_biz_type(session, records):
    user = _user(session, "salary_user")
    with pytest.raises(HTTPException) as exc:
        _call(session, user, ["salary.view"], biz_type="order", biz_id=1)
    assert exc.value.status_code == 403


def test_record_list_rejects_unknown_biz_type(session, records):
    user = _user(session, "root", superuser=True)
    with pytest.raises(HTTPException) as exc:
        _call(session, user, [], biz_type="unknown", biz_id=1)
    assert exc.value.status_code == 400


def test_superuser_sees_all_records(session, records):
    root = _user(session, "root", superuser=True)
    data = _call(session, root, [])
    assert data["data"]["total"] == 3


def test_list_records_biz_types_filter(session, records):
    items, total = list_records(session, biz_types=["order", "statement"])
    assert total == 2
    assert {r.biz_type for r in items} == {"order", "statement"}
