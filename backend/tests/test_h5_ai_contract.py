# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""H5 智能中心契约测试。

两条护栏：
1. frontend-h5/src/api/ai.ts 里调用的 /extensions/* 接口，必须真的在后端
   某个 extensions/*/router.py 注册过——防止前端调了空路由，等到点了才 404。
2. ai_assistant 的会话续接：chat/agent 传 conversation_id 时复用同一会话，
   且校验会话归属（不能用别人的会话串上下文）。

注意：backend/extensions/ 是运行期安装的商业扩展（.gitignore 忽略），源码在
私有仓库 mes-extensions。公开仓库的干净检出里没有这些 router.py，因此依赖
扩展源码的用例自动跳过；只依赖 frontend-h5/src/api/ai.ts 的用例始终运行。
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

AI_TS = REPO / "frontend-h5" / "src" / "api" / "ai.ts"
EXT_DIR = BACKEND / "extensions"
HAS_EXT = EXT_DIR.is_dir() and any(EXT_DIR.glob("*/router.py"))

METHOD = {"apiGet": "get", "apiPost": "post", "apiPut": "put", "apiPatch": "patch", "apiDelete": "delete"}
CALL_RE = re.compile(r"api(Get|Post|Put|Patch|Delete)(?:<[^>]*>)?\(\s*(['\x60\"])([^'\x60\"]+)\2", re.S)
ROUTE_RE = re.compile(r"@router\.(get|post|put|patch|delete)\(\s*['\x22]([^'\x22]+)['\x22]")


def _frontend_calls() -> set[tuple[str, str]]:
    src = AI_TS.read_text(encoding="utf-8")
    out = set()
    for m in CALL_RE.finditer(src):
        path = m.group(3)
        if not path.startswith("/extensions/"):
            continue
        # 模板字符串里的 ${id} 对应后端路径参数 {conv_id}
        path = re.sub(r"\$\{[^}]+\}", "{}", path).rstrip("/")
        out.add((METHOD["api" + m.group(1)], path))
    return out


def _backend_routes() -> set[tuple[str, str]]:
    out = set()
    for rp in sorted(EXT_DIR.glob("*/router.py")):
        key = rp.parent.name
        for m in ROUTE_RE.finditer(rp.read_text(encoding="utf-8")):
            path = ("/extensions/" + key + "/" + m.group(2).lstrip("/")).rstrip("/")
            path = re.sub(r"\{[^}]+\}", "{}", path)
            out.add((m.group(1), path))
    return out


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_h5_ai_endpoints_all_exist():
    calls = _frontend_calls()
    assert len(calls) >= 20, f"扫描到的前端扩展调用太少（{len(calls)}），正则可能失效"
    routes = _backend_routes()
    missing = sorted(c for c in calls if c not in routes)
    assert not missing, "前端调用但后端未注册: " + ", ".join(f"{m} {p}" for m, p in missing)


def test_h5_ai_contract_covers_new_capabilities():
    """第二批接入的能力必须真的在 ai.ts 里有封装，防止功能被回退掉。"""
    calls = {p for _m, p in _frontend_calls()}
    required = {
        "/extensions/ai_assistant/conversations",
        "/extensions/ai_assistant/conversations/{}",
        "/extensions/ai_anomaly/summary",
        "/extensions/ai_anomaly/options",
        "/extensions/ai_insight/axes",
        "/extensions/ai_insight/runs",
        "/extensions/ai_employee/logs",
        "/extensions/ai_employee/toggle",
        "/extensions/ai_scene_reports/docs",
        "/extensions/ai_scene_reports/preview",
        "/extensions/ai_scene_reports/docs/{}",
    }
    missing = sorted(required - calls)
    assert not missing, "缺少第二批能力封装: " + ", ".join(missing)



def test_h5_ai_contract_covers_batch3_capabilities():
    """第三批接入的能力必须真的在 ai.ts 里有封装，防止功能被回退掉。"""
    calls = {(m, p) for m, p in _frontend_calls()}
    required = {
        ("patch", "/extensions/ai_assistant/conversations/{}"),
        ("post", "/extensions/ai_knowledge/search"),
        ("post", "/extensions/ai_knowledge/ask"),
        ("get", "/extensions/ai_knowledge/status"),
    }
    missing = sorted(required - calls)
    assert not missing, "缺少第三批能力封装: " + ", ".join(f"{m} {p}" for m, p in missing)


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_rename_conversation_rejects_blank(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    body = mod.ConversationRenameIn(title="   ")
    out = mod.rename_conversation(7, body, db=db, user=MagicMock(id=3))["data"]
    assert out["ok"] is False and out["updated"] is False
    db.execute.assert_not_called()


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_rename_conversation_scoped_to_current_user(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    seen = {}

    def fake_rows(_db, sql, **params):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(mod, "_rows", fake_rows)
    body = mod.ConversationRenameIn(title="新标题")
    out = mod.rename_conversation(7, body, db=db, user=MagicMock(id=3))["data"]
    assert out["found"] is False and out["updated"] is False
    assert "user_id=:uid" in seen["sql"]
    assert seen["params"]["uid"] == 3 and seen["params"]["cid"] == 7
    db.execute.assert_not_called()


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_rename_conversation_updates_owned(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    monkeypatch.setattr(mod, "_rows", lambda *a, **k: [{"id": 7}])
    body = mod.ConversationRenameIn(title="  交接班问题  ")
    out = mod.rename_conversation(7, body, db=db, user=MagicMock(id=3))["data"]
    assert out["ok"] is True and out["title"] == "交接班问题"
    sql, params = db.execute.call_args[0][0], db.execute.call_args[0][1]
    assert "UPDATE ext_ai_conversations SET title=:t" in str(sql)
    assert params["t"] == "交接班问题" and params["cid"] == 7
    db.commit.assert_called_once()

def _assistant():
    try:
        return importlib.import_module("extensions.ai_assistant.router")
    except ModuleNotFoundError:
        pytest.skip("ai_assistant 扩展未安装（源码在私有仓库 mes-extensions）")


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_conversation_resumes_existing_id(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    monkeypatch.setattr(mod, "_rows", lambda *a, **k: [{"id": 42}])
    assert mod._ensure_conversation(db, 7, "继续聊", "assistant", 42) == 42
    db.execute.assert_not_called()


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_conversation_scoped_to_current_user(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    seen = {}

    def fake_rows(_db, sql, **params):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(mod, "_rows", fake_rows)
    monkeypatch.setattr(mod, "_scalar", lambda *a, **k: 99)
    mod._ensure_conversation(db, 7, "hi", "assistant", 42)
    assert "user_id=:uid" in seen["sql"]
    assert seen["params"]["uid"] == 7 and seen["params"]["cid"] == 42


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_conversation_creates_new_when_missing(monkeypatch):
    mod = _assistant()
    db = MagicMock()
    monkeypatch.setattr(mod, "_rows", lambda *a, **k: [])
    monkeypatch.setattr(mod, "_scalar", lambda *a, **k: 99)
    assert mod._ensure_conversation(db, 7, "hi", "assistant", None) == 99
    assert db.execute.call_count == 1
    db.commit.assert_called_once()
