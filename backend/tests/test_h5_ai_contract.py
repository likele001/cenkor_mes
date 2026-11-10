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


# ── 第四批：扩展状态预检查 / 预警批量处置 ──────────────────────────────────

def test_h5_ai_contract_covers_batch4_capabilities():
    """第四批新增的两个封装必须留在 ai.ts，防止功能被回退掉。"""
    calls = {(m, p) for m, p in _frontend_calls()}
    assert ("post", "/extensions/ai_anomaly/alerts/batch-handle") in calls
    assert "'/h5/ai/extensions'" in AI_TS.read_text(encoding="utf-8")


def test_h5_ai_extension_status_route_wired():
    """H5 状态接口必须真的挂进 /h5 路由，且只按登录用户返回三态。"""
    src = (BACKEND / "app/api/h5/ai_extensions.py").read_text(encoding="utf-8")
    assert 'prefix="/ai/extensions"' in src
    assert '@router.get("")' in src
    assert "runtime.is_enabled" in src
    assert "get_user_permission_codes(db, user.id)" in src
    assert "status_list" not in src  # 不暴露管理端完整状态
    router_src = (BACKEND / "app/api/h5/router.py").read_text(encoding="utf-8")
    assert "h5_ai_extensions_router" in router_src


def test_ai_extension_status_three_states(monkeypatch):
    """未安装 / 已停用 / 已授权三态同时成立，且不依赖商业扩展源码。"""
    try:
        from app.api.h5 import ai_extensions as mod
    except Exception as e:  # noqa: BLE001 - 干净检出缺依赖时降级为跳过
        pytest.skip(f"H5 状态模块导入失败: {e}")
    db = MagicMock()
    monkeypatch.setattr(mod.runtime, "installed", {"ai_assistant": {}, "ai_insight": {}})
    monkeypatch.setattr(mod.runtime, "is_enabled", lambda key: key == "ai_assistant")
    monkeypatch.setattr(mod, "get_user_permission_codes",
                        lambda _db, uid: ["ext.ai_assistant.view"])
    out = mod.list_ai_extensions(db=db, user=MagicMock(id=3))["data"]
    items = {x["key"]: x for x in out["items"]}
    assert out["installed_total"] == 2
    assert items["ai_assistant"]["enabled"] is True
    assert items["ai_assistant"]["granted"] is True
    assert items["ai_insight"]["installed"] is True and items["ai_insight"]["enabled"] is False
    assert items["ai_anomaly"]["installed"] is False


def _anomaly():
    try:
        return importlib.import_module("extensions.ai_anomaly.router")
    except ModuleNotFoundError:
        pytest.skip("ai_anomaly 扩展未安装（源码在私有仓库 mes-extensions）")


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_batch_handle_rejects_invalid_status():
    mod = _anomaly()
    db = MagicMock()
    out = mod.batch_handle(mod.BatchHandleIn(ids=[1, 2], status="bogus"), db=db)["data"]
    assert out["ok"] is False and out["total"] == 0
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_batch_handle_dedups_and_reports_missing(monkeypatch):
    mod = _anomaly()
    db = MagicMock()
    seen = {}

    def fake_rows(_db, sql, **params):
        seen["sql"], seen["params"] = sql, params
        return [{"id": 1}, {"id": 3}]

    monkeypatch.setattr(mod, "_rows", fake_rows)
    out = mod.batch_handle(
        mod.BatchHandleIn(ids=[1, 1, 2, 3], status="resolved"), db=db)["data"]
    assert out["ok"] is True and out["total"] == 2
    assert out["succeeded"] == [1, 3]
    assert out["missing"] == [2]
    assert seen["params"] == {"i0": 1, "i1": 2, "i2": 3}
    assert db.execute.call_count == 2
    first_sql = str(db.execute.call_args_list[0][0][0])
    assert "handled_at=NOW()" in first_sql
    assert db.execute.call_args_list[0][0][1] == {"s": "resolved", "i": 1}
    db.commit.assert_called_once()


# ── 第五批：预警详情闭环 / 列表完整性 / 助手失败重试 ────────────────────────

def test_h5_ai_contract_covers_batch5_capabilities():
    """第五批防回退：类型字段、limit、详情弹层与失败重试入口都必须在。"""
    src = AI_TS.read_text(encoding="utf-8")
    assert "limit?: number" in src
    assert "severity?: string" in src
    assert "ai_insight?: string | null" in src
    alerts = (REPO / "frontend-h5/src/pages/AiAlertsPage.vue").read_text(encoding="utf-8")
    for marker in ("getAlertDetail(", "refreshInsight", "loadMore", "exportAlertsCsv",
                   "doBatch('open')", "changeStatus(", "sevOf("):
        assert marker in alerts, f"预警页缺少第五批能力: {marker}"
    assist = (REPO / "frontend-h5/src/pages/AiAssistantPage.vue").read_text(encoding="utf-8")
    for marker in ("retryFailed(", "autoNameIfNew(", "autoTitle("):
        assert marker in assist, f"助手页缺少第五批能力: {marker}"


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_alert_detail_exposes_full_fields(monkeypatch):
    """详情弹层依赖的完整字段必须真的由后端返回，且严重度字段是 severity。"""
    mod = _anomaly()
    db = MagicMock()
    row = {
        "id": 7, "dim": "quality", "code": "Q1", "severity": "critical", "score": 9.5,
        "title": "缺陷率异常", "entity_type": "wo", "entity_id": 3, "entity_name": "WO-1",
        "detail": "缺陷率上升", "root_cause": "设备偏移", "suggestion": "停机点检",
        "facts_json": '{"defect_rate": 0.12}', "status": "open",
        "ai_insight": "已缓存解读", "ai_insight_at": "2026-11-10 10:00",
        "first_seen_at": "2026-11-09 08:00", "last_seen_at": "2026-11-10 09:00",
    }
    monkeypatch.setattr(mod, "_rows", lambda *a, **k: [row])
    out = mod.alert_detail(7, db=db)["data"]
    assert out["found"] is True
    a = out["alert"]
    assert a["severity"] == "critical" and "level" not in a
    assert a["facts"] == {"defect_rate": 0.12}
    assert a["ai_insight"] == "已缓存解读"
    assert a["first_seen_at"] and a["last_seen_at"]


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_batch_handle_reopen_clears_handled_at(monkeypatch):
    """批量恢复待处理（status=open）必须清掉 handled_at，否则状态与时间自相矛盾。"""
    mod = _anomaly()
    db = MagicMock()
    monkeypatch.setattr(mod, "_rows", lambda *a, **k: [{"id": 4}])
    out = mod.batch_handle(mod.BatchHandleIn(ids=[4], status="open"), db=db)["data"]
    assert out["ok"] is True and out["status"] == "open"
    sql = str(db.execute.call_args_list[0][0][0])
    assert "handled_at=NULL" in sql
    assert db.execute.call_args_list[0][0][1] == {"s": "open", "i": 4}


# ── 第六批：个人留痕隔离 / 洞察历史治理 / 巡检指令 ──────────────────────────

def test_h5_ai_contract_covers_batch6_capabilities():
    """第六批防回退：个人留痕走 mine、洞察历史可删可复制、员工可下指令、文书可筛可复制。"""
    src = AI_TS.read_text(encoding="utf-8")
    for marker in ("mine?: number", "listKnowledgeLogs", "deleteInsightRun("):
        assert marker in src, f"ai.ts 缺少第六批封装: {marker}"

    clip = (REPO / "frontend-h5/src/utils/clipboard.ts").read_text(encoding="utf-8")
    assert "export async function copyText" in clip

    help_page = (REPO / "frontend-h5/src/pages/HelpPage.vue").read_text(encoding="utf-8")
    for marker in ("listKnowledgeLogs({ mine: 1", "replayServer(", "helpServerHistory"):
        assert marker in help_page, f"帮助页缺少第六批能力: {marker}"

    insight = (REPO / "frontend-h5/src/pages/AiInsightPage.vue").read_text(encoding="utf-8")
    for marker in ("copyRun(", "removeRun(", "deleteInsightRun("):
        assert marker in insight, f"洞察页缺少第六批能力: {marker}"

    emp = (REPO / "frontend-h5/src/pages/AiEmployeesPage.vue").read_text(encoding="utf-8")
    for marker in ("instruction.value.trim() || undefined", "reloadLogs(", "logTool", "logStatus"):
        assert marker in emp, f"员工页缺少第六批能力: {marker}"

    scene = (REPO / "frontend-h5/src/pages/AiScenePage.vue").read_text(encoding="utf-8")
    for marker in ("copyDoc(", "docType.value || undefined", "loadMoreDocs("):
        assert marker in scene, f"文书页缺少第六批能力: {marker}"


def _knowledge():
    try:
        return importlib.import_module("extensions.ai_knowledge.router")
    except ModuleNotFoundError:
        pytest.skip("ai_knowledge 扩展未安装（源码在私有仓库 mes-extensions）")


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_knowledge_logs_mine_scoped_to_current_user(monkeypatch):
    """mine=1 必须按 created_by 过滤，否则员工端能看到别人的提问。"""
    mod = _knowledge()
    seen = {}

    def fake_rows(_db, sql, **params):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(mod, "_rows", fake_rows)
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)
    monkeypatch.setattr(mod, "_has_ai_model_col", lambda _db: True)
    user = MagicMock()
    user.id = 42
    out = mod.list_logs(page=1, page_size=20, mine=1, db=MagicMock(), user=user)["data"]
    assert out["mine"] is True and out["items"] == []
    assert "created_by = :uid" in seen["sql"]
    assert seen["params"]["uid"] == 42
    assert seen["params"]["lim"] == 20


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_knowledge_logs_default_keeps_global_view(monkeypatch):
    """管理端/后台仍要能看全局留痕：不带 mine 时不得加 created_by 条件。"""
    mod = _knowledge()
    seen = {}

    def fake_rows(_db, sql, **params):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(mod, "_rows", fake_rows)
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)
    monkeypatch.setattr(mod, "_has_ai_model_col", lambda _db: True)
    out = mod.list_logs(page=1, page_size=20, mine=0, db=MagicMock(), user=MagicMock())["data"]
    assert out["mine"] is False
    assert "created_by" not in seen["sql"]
    assert "uid" not in seen["params"]


# ── 第七批：知识库资料浏览 / 洞察批量清理 ──────────────────────────────────

def test_h5_ai_contract_covers_batch7_capabilities():
    """第七批防回退：资料页可列可读、入口与路由齐备，洞察历史支持多选批量删除。"""
    src = AI_TS.read_text(encoding="utf-8")
    for marker in ("listKnowledgeDocs", "getKnowledgeDoc(", "batchDeleteInsightRuns("):
        assert marker in src, f"ai.ts 缺少第七批封装: {marker}"

    docs_page = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    for marker in ("listKnowledgeDocs(", "getKnowledgeDoc(", "copyDetail(", "pickScope("):
        assert marker in docs_page, f"资料页缺少第七批能力: {marker}"

    router = (REPO / "frontend-h5/src/router/index.ts").read_text(encoding="utf-8")
    assert "ai-docs" in router and "AiDocsPage.vue" in router

    hub = (REPO / "frontend-h5/src/pages/AiHubPage.vue").read_text(encoding="utf-8")
    assert "/ai-docs" in hub and "ext.ai_knowledge.view" in hub

    insight = (REPO / "frontend-h5/src/pages/AiInsightPage.vue").read_text(encoding="utf-8")
    for marker in ("removeSelected(", "toggleSelectMode(", "batchDeleteInsightRuns("):
        assert marker in insight, f"洞察页缺少第七批能力: {marker}"


def test_h5_ai_extension_status_covers_knowledge():
    """资料页也要参与扩展预检查，否则首页卡片无法标注未开通/未授权。"""
    from app.api.h5 import ai_extensions as mod
    perms = dict(mod.AI_EXTENSIONS)
    assert perms.get("ai_knowledge") == "ext.ai_knowledge.view"


def _insight_ext():
    try:
        return importlib.import_module("extensions.ai_insight.router")
    except ModuleNotFoundError:
        pytest.skip("ai_insight 扩展未安装（源码在私有仓库 mes-extensions）")


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_insight_batch_delete_dedups_and_reports_missing(monkeypatch):
    """批量软删要先去重，再把已不存在的 id 回传，前端才能提示部分成功。"""
    mod = _insight_ext()
    db = MagicMock()
    monkeypatch.setattr(mod, "_safe_rows", lambda _db, sql, **p: [{"id": 2}, {"id": 4}])
    out = mod.batch_delete_runs(mod.BatchDeleteIn(ids=[4, 2, 2, 9]), db=db)["data"]
    assert out["ok"] is True and out["total"] == 3
    assert out["succeeded"] == [2, 4]
    assert out["missing"] == [9]
    sql = str(db.execute.call_args_list[0][0][0])
    assert "deleted_at = NOW()" in sql
    assert db.execute.call_args_list[0][0][1] == {"f0": 2, "f1": 4}
    db.commit.assert_called_once()


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_insight_batch_delete_rejects_empty_and_oversize(monkeypatch):
    """空选与超过 50 条都要在入口拦住，不能靠前端自觉。"""
    mod = _insight_ext()
    db = MagicMock()
    monkeypatch.setattr(mod, "_safe_rows", lambda *a, **k: [])
    out = mod.batch_delete_runs(mod.BatchDeleteIn(ids=[0, -1]), db=db)["data"]
    assert out["ok"] is False and out["total"] == 0
    db.execute.assert_not_called()
    with pytest.raises(ValueError):
        mod.BatchDeleteIn(ids=list(range(1, 52)))
