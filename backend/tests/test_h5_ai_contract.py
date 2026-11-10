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

# ── 第八批：资料页「问这篇」（doc_id 限定检索）与洞察导出 ──────────────────

@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_knowledge_search_accepts_doc_id_scope():
    """问这篇靠 doc_id 限定范围；不传必须留空，默认行为仍是全库检索。"""
    mod = _knowledge()
    assert mod.SearchIn(query="换型步骤").doc_id is None
    assert mod.SearchIn(query="换型步骤", doc_id=12).doc_id == 12
    with pytest.raises(ValueError):
        mod.SearchIn(query="换型步骤", doc_id=0)  # ge=1，0 不是合法文档 id


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_knowledge_doc_guard_blocks_invisible_doc(monkeypatch):
    """知道 id 不等于有权限：查不到目标文档就要拦掉，不能悄悄退化成全库检索。"""
    mod = _knowledge()
    db = MagicMock()
    # 不指定文档时不查库，直接放行（全库路径不接受多余查询）
    assert mod._doc_scope_guard(db, None, "1=1", {}) == ""
    db.execute.assert_not_called()
    monkeypatch.setattr(mod, "_safe_rows", lambda *a, **k: [])
    assert mod._doc_scope_guard(db, 42, "1=1", {}) != ""
    monkeypatch.setattr(mod, "_safe_rows", lambda *a, **k: [{"id": 42}])
    assert mod._doc_scope_guard(db, 42, "1=1", {}) == ""


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_knowledge_retrieve_scopes_both_paths_to_doc():
    """向量与关键词两条路径都要按 doc_id 收口，只堵一条等于没堵。"""
    mod = _knowledge()
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "def _retrieve(db, query: str, top_k: int, scope: str, where: str, args: dict," in src
    assert 'if only and c["doc_id"] != only:' in src
    assert "c.doc_id = :only_doc" in src
    # 单篇时候选窗口要放大，否则别的文档占满 recall，过滤后可能一篇不剩
    assert "400 if only else 0" in src
    assert "2000 if only else 0" in src


def test_h5_ai_contract_covers_batch8_capabilities():
    """资料页「问这篇」与洞察导出必须真的落在页面上，防止后续重构抹掉。"""
    ai = AI_TS.read_text(encoding="utf-8")
    assert "export function knowledgeAsk(query: string, useLlm = true, topK = 5, docId?: number)" in ai
    assert "...(docId ? { doc_id: docId } : {})" in ai
    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    assert "knowledgeAsk(q, true, 5, doc.id)" in docs
    assert "t('ai.docsAskTitle')" in docs
    assert "t('ai.docsAskFallback')" in docs
    insight = (REPO / "frontend-h5/src/pages/AiInsightPage.vue").read_text(encoding="utf-8")
    assert "function exportRuns()" in insight
    assert "t('ai.runExport')" in insight
    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("docsAskTitle", "docsAskFallback", "runExport", "runColExcerpt"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第九批：跨页溯源（问答依据 → 全文、预警 → 相关制度）─────────────────────

def test_h5_ai_contract_covers_batch9_capabilities():
    """答案里的《文档名》要能点开、预警要能直接查制度；跳转参数与落地页必须对得上。"""
    help_page = (REPO / "frontend-h5/src/pages/HelpPage.vue").read_text(encoding="utf-8")
    assert "function openSourceDoc(h: KnowledgeHit)" in help_page
    assert "void router.push({ name: 'aiDocs', query: { doc: String(h.doc_id) } })" in help_page
    assert "v-if=\"h.doc_id\"" in help_page  # 基础帮助的 sources 没有 doc_id，不能给死链

    docs_page = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    assert "const docId = Number(route.query.doc || 0)" in docs_page
    assert "if (docId > 0) await openDoc(docId)" in docs_page
    assert "watch(() => [route.query.doc, route.query.q]" in docs_page

    alerts_page = (REPO / "frontend-h5/src/pages/AiAlertsPage.vue").read_text(encoding="utf-8")
    assert "function findDocs()" in alerts_page
    assert "detail.value?.dim_label || detail.value?.title" in alerts_page

    # 落地页路由名必须是 aiDocs，否则三处 router.push 全成死链
    router = (REPO / "frontend-h5/src/router/index.ts").read_text(encoding="utf-8")
    assert re.search(r"name: 'aiDocs'[^}]*AiDocsPage", router) or "aiDocs" in router

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("helpOpenDoc", "alertFindDocs"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第十批：会话搜索与洞察历史维度筛选 ──────────────────────────────────────

def test_h5_ai_contract_covers_batch10_capabilities():
    """筛选要真的带进请求、列表要真的用过滤结果，否则界面点着没反应。"""
    chat = (REPO / "frontend-h5/src/pages/AiAssistantPage.vue").read_text(encoding="utf-8")
    assert "const filteredConversations = computed" in chat
    assert 'v-for="c in filteredConversations"' in chat
    assert "historyKeyword.trim() ? t('ai.convSearchEmpty')" in chat

    insight = (REPO / "frontend-h5/src/pages/AiInsightPage.vue").read_text(encoding="utf-8")
    assert "const runAxis = ref('')" in insight
    assert "listInsightRuns({ axis: runAxis.value || undefined, page_size: 30 })" in insight
    assert "function pickRunAxis(code: string)" in insight

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("convSearchPlaceholder", "convSearchEmpty", "runFilterAll"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第十一批：员工执行日志按人隔离 + 执行明细 ────────────────────────────────

def _employee_ext():
    try:
        return importlib.import_module("extensions.ai_employee.router")
    except ModuleNotFoundError:
        pytest.skip("ai_employee 扩展未安装（源码在私有仓库 mes-extensions）")


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_employee_logs_mine_scoped_to_current_user(monkeypatch):
    """/logs 原本是全站时间线，员工端必须能按人收回来，否则别人的巡检结果全可见。"""
    mod = _employee_ext()
    calls = {"sql": [], "args": []}

    def fake_rows(_db, sql, **p):
        calls["sql"].append(sql)
        calls["args"].append(p)
        return []

    monkeypatch.setattr(mod, "_rows", fake_rows)
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)
    out = mod.logs(mine=1, limit=10, offset=0, db=MagicMock(), user=MagicMock(id=9))["data"]
    assert out["mine"] is True
    assert "user_id=:uid" in calls["sql"][0]
    assert calls["args"][0]["uid"] == 9


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_employee_logs_default_keeps_global_view(monkeypatch):
    """管理端不传 mine，行为必须保持全站，不能顺手把管理视图也收窄。"""
    mod = _employee_ext()
    calls = []
    monkeypatch.setattr(mod, "_rows", lambda _db, sql, **p: calls.append(sql) or [])
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)
    out = mod.logs(mine=0, limit=10, offset=0, db=MagicMock(), user=MagicMock(id=9))["data"]
    assert out["mine"] is False
    assert "user_id=:uid" not in calls[0]


@pytest.mark.skipif(not HAS_EXT, reason="商业扩展源码在私有仓库，公开仓库跳过")
def test_employee_log_detail_scoped_and_parses_facts(monkeypatch):
    """明细要限本人；有 manage 才放开全站；facts_json 要解析成对象给前端。"""
    mod = _employee_ext()
    captured = {}

    def fake_rows(_db, sql, **p):
        captured["sql"], captured["args"] = sql, p
        return [{"id": 3, "tool_code": "prod_daily", "facts_json": '{"lines": 2}'}]

    monkeypatch.setattr(mod, "_safe_rows", fake_rows)
    monkeypatch.setattr(mod, "_can_manage", lambda *a: False)
    out = mod.log_detail(3, db=MagicMock(), user=MagicMock(id=5))["data"]
    assert out["found"] is True
    assert out["facts"] == {"lines": 2}
    assert out["manage"] is False
    assert "user_id=:uid" in captured["sql"]
    assert captured["args"]["uid"] == 5

    monkeypatch.setattr(mod, "_can_manage", lambda *a: True)
    out2 = mod.log_detail(3, db=MagicMock(), user=MagicMock(id=5))["data"]
    assert out2["manage"] is True
    assert "user_id=:uid" not in captured["sql"]


def test_h5_ai_contract_covers_batch11_capabilities():
    """员工端日志要带 mine=1，明细按钮与弹层真的接上，否则等于没隔离。"""
    ai = AI_TS.read_text(encoding="utf-8")
    assert "export function getEmployeeLog(id: number)" in ai
    assert "/extensions/ai_employee/logs/${id}" in ai
    page = (REPO / "frontend-h5/src/pages/AiEmployeesPage.vue").read_text(encoding="utf-8")
    assert "mine: 1," in page
    assert "function openLog(id: number)" in page
    assert "getEmployeeLog(id)" in page
    assert "t('ai.logFacts')" in page
    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("logDetail", "logInstruction", "logFacts", "logTokens"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第十二批：详情复制 / 资料页最近浏览 / 命中片段复制 ────────────────────────

def test_h5_ai_contract_covers_batch12_capabilities():
    """复制与最近浏览都要真接上，不能只有按钮没实现。"""
    alerts = (REPO / "frontend-h5/src/pages/AiAlertsPage.vue").read_text(encoding="utf-8")
    assert "async function copyAlertDetail()" in alerts
    assert "copyToClipboard(lines.join(" in alerts
    assert "@click=\"copyAlertDetail\"" in alerts

    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    assert "const RECENT_KEY = 'cenkormes_h5_ai_docs_recent'" in docs
    assert "function pushRecent(d: KnowledgeDoc)" in docs
    assert "loadRecent()" in docs
    # 打开详情成功后才记，否则失败了也进「最近浏览」
    assert "detail.value = r\n    pushRecent(r)" in docs

    help_page = (REPO / "frontend-h5/src/pages/HelpPage.vue").read_text(encoding="utf-8")
    assert "async function copyHit(h: KnowledgeHit)" in help_page
    assert "t('ai.helpCopySnippet')" in help_page

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("recentDocs", "recentClear", "helpCopySnippet"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第十三批：AI 用量可见（模型 / token）────────────────────────────────────

def test_h5_ai_contract_covers_batch13_capabilities():
    """用量要真的从接口透到页面：类型丢字段会让 ts 报错，这里再兜一层防回退。"""
    ai = AI_TS.read_text(encoding="utf-8")
    assert "  tokens_in?: number | null" in ai
    assert "tokens_in: r.tokens_in," in ai

    chat = (REPO / "frontend-h5/src/pages/AiAssistantPage.vue").read_text(encoding="utf-8")
    assert "tokens?: { i: number; o: number }" in chat
    assert "t('ai.usageTokens', { i: m.tokens.i, o: m.tokens.o })" in chat

    help_page = (REPO / "frontend-h5/src/pages/HelpPage.vue").read_text(encoding="utf-8")
    assert "const usage = ref<{ i: number; o: number; m: string } | null>(null)" in help_page
    assert "t('ai.usageModel', { m: usage.m })" in help_page

    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    assert "const askUsage = ref<{ i: number; o: number } | null>(null)" in docs
    assert "t('ai.usageTokens', { i: askUsage.i, o: askUsage.o })" in docs

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("usageTokens", "usageModel"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"

# ── 第十四批：报告 / 文书导出 Markdown ──────────────────────────────────────

def test_h5_ai_contract_covers_batch14_capabilities():
    """导出走统一工具，两个页面都要真的接上，别各写一份 Blob 逻辑。"""
    dl = REPO / "frontend-h5/src/utils/download.ts"
    assert dl.is_file(), "缺少统一的下载工具"
    src = dl.read_text(encoding="utf-8")
    assert "export function downloadText(" in src
    assert "URL.createObjectURL" in src and "revokeObjectURL" in src

    insight = (REPO / "frontend-h5/src/pages/AiInsightPage.vue").read_text(encoding="utf-8")
    assert "import { downloadText } from '@/utils/download'" in insight
    assert "async function exportRunMd(r: InsightRun)" in insight
    assert "exportRunMd(r)" in insight

    scene = (REPO / "frontend-h5/src/pages/AiScenePage.vue").read_text(encoding="utf-8")
    assert "import { downloadText } from '@/utils/download'" in scene
    assert "async function exportDocMd(id: number)" in scene
    assert "exportDocMd(d.id)" in scene

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        assert "exportMd:" in pack, f"{loc} 缺 exportMd"


# ── 第十五批：资料排序 / 向量化筛选 / 首页最近使用 ──────────────────────────

def test_knowledge_doc_order_whitelist_only():
    """ORDER BY 是拼 SQL 的入口：白名单之外（包括注入串）必须回落默认排序。"""
    mod = _knowledge()
    assert mod._doc_order(None) == "d.id DESC"
    assert mod._doc_order("updated") == "d.updated_at DESC, d.id DESC"
    assert mod._doc_order("TITLE ") == "d.title ASC, d.id DESC"
    assert mod._doc_order("long") == "CHAR_LENGTH(COALESCE(d.content,'')) DESC, d.id DESC"
    for bad in ("", "id desc; DROP TABLE users", "updated_at", "-id"):
        assert mod._doc_order(bad) == "d.id DESC", f"未拦截非法排序 {bad!r}"


def test_knowledge_list_docs_applies_sort_and_vectorized_filter(monkeypatch):
    """排序与向量化筛选要真的进 SQL；未传时不加条件（管理端/老前端行为不变）。"""
    mod = _knowledge()
    monkeypatch.setattr(mod, "_is_manager", lambda user, db: False)
    monkeypatch.setattr(mod, "_visibility", lambda db, user, manage: ("1=1", {}))
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)

    captured = {}

    def fake_rows(db, sql, **kw):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(mod, "_safe_rows", fake_rows)
    db, user = MagicMock(), MagicMock(id=3)

    mod.list_docs(q=None, scope=None, sort="updated", vectorized=0, source=None,
                  page=1, page_size=20, db=db, user=user)
    sql = captured["sql"]
    assert "ORDER BY d.updated_at DESC, d.id DESC" in sql
    assert "(d.vectorized = 0 OR d.vectorized IS NULL)" in sql

    mod.list_docs(q=None, scope=None, sort=None, vectorized=1, source=None,
                  page=1, page_size=20, db=db, user=user)
    sql = captured["sql"]
    assert "ORDER BY d.id DESC" in sql
    assert "AND d.vectorized = 1" in sql

    mod.list_docs(q=None, scope=None, sort=None, vectorized=None, source=None,
                  page=1, page_size=20, db=db, user=user)
    sql = captured["sql"]
    where = sql.split(" WHERE ", 1)[1].split(" ORDER BY ", 1)[0]
    assert "vectorized" not in where, "未筛选时 WHERE 不应带向量化条件"


def test_h5_ai_contract_covers_batch15_capabilities():
    """排序/筛选下沉后端、最近使用只记本机：前端与三语都要真的接上。"""
    ai = AI_TS.read_text(encoding="utf-8")
    for marker in ("sort?: string", "vectorized?: number"):
        assert marker in ai, f"ai.ts 缺少列表参数: {marker}"

    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    for marker in ("const sortMode = ref('new')", "const vecMode = ref('')",
                   "function pickSort(", "function pickVec(",
                   "sort: sortMode.value",
                   "vectorized: vecMode.value === '' ? undefined : Number(vecMode.value)"):
        assert marker in docs, f"资料页缺少第十五批能力: {marker}"

    hub = (REPO / "frontend-h5/src/pages/AiHubPage.vue").read_text(encoding="utf-8")
    for marker in ("cenkormes_h5_ai_hub_recent", "const recentEntries = computed<Entry[]>(",
                   "function pushRecent(", "pushRecent(e.path)"):
        assert marker in hub, f"智能中心缺少最近使用: {marker}"

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("docsSortUpdated", "docsVecNone", "hubRecent"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"


# ── 第十六批：首页今日概览 ──────────────────────────────────────────────────

def test_h5_ai_contract_covers_batch16_capabilities():
    """概览只允许向「当前用户能进」的扩展取数，且失败不能拖垮首页。"""
    hub = (REPO / "frontend-h5/src/pages/AiHubPage.vue").read_text(encoding="utf-8")

    for marker in ("getAnomalySummary", "employeeOverview"):
        assert marker in hub, f"首页概览缺少数据源: {marker}"

    # 取数前必须过 allowed()（扩展未开通 / 停用 / 未授权时不发请求）
    assert "if (allowed('/ai-alerts'))" in hub
    assert "if (allowed('/ai-employees'))" in hub
    # 任一接口失败只少一项，不许抛到调用方
    assert hub.count("} catch {") >= 2
    assert "overview.value = { health: null, active: null, runs: null }" in hub, "刷新前必须清空旧值"

    for key in ("hubOverview", "hubMetricHealth", "hubMetricActive", "hubMetricRuns"):
        for loc in ("zh-CN", "en-US", "ko-KR"):
            pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
            assert f"{key}:" in pack, f"{loc} 缺 {key}"


# ── 第十七批：同来源资料 / 全部会话导出 ────────────────────────────────────

def test_knowledge_list_docs_filters_by_source(monkeypatch):
    """按来源筛要落到 SQL（同一份制度拆多篇时才有用），不传时不能加条件。"""
    mod = _knowledge()
    monkeypatch.setattr(mod, "_is_manager", lambda user, db: False)
    monkeypatch.setattr(mod, "_visibility", lambda db, user, manage: ("1=1", {}))
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)

    captured = {}

    def fake_rows(db, sql, **kw):
        captured["sql"] = sql
        captured["args"] = kw
        return []

    monkeypatch.setattr(mod, "_safe_rows", fake_rows)
    db, user = MagicMock(), MagicMock(id=3)

    mod.list_docs(q=None, scope=None, sort=None, vectorized=None,
                  source=" 安全管理制度 ", page=1, page_size=20, db=db, user=user)
    assert "AND d.source LIKE :src" in captured["sql"]
    assert captured["args"]["src"] == "%安全管理制度%"

    mod.list_docs(q=None, scope=None, sort=None, vectorized=None,
                  source=None, page=1, page_size=20, db=db, user=user)
    where = captured["sql"].split(" WHERE ", 1)[1].split(" ORDER BY ", 1)[0]
    assert "source" not in where


def test_h5_ai_contract_covers_batch17_capabilities():
    """同来源筛选与全部会话导出都要真的接上。"""
    ai = AI_TS.read_text(encoding="utf-8")
    assert "source?: string" in ai

    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    for marker in ("const activeSource = ref('')", "source: activeSource.value || undefined",
                   "function filterBySource(", "function clearSource("):
        assert marker in docs, f"资料页缺少同来源筛选: {marker}"

    chat = (REPO / "frontend-h5/src/pages/AiAssistantPage.vue").read_text(encoding="utf-8")
    for marker in ("import { downloadText } from '@/utils/download'",
                   "const EXPORT_LIMIT = 30", "async function exportAllChats(",
                   '@click="exportAllChats"'):
        assert marker in chat, f"助手页缺少全部导出: {marker}"

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("docsSameSource", "exportAll", "exportAllPartial"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"


def test_knowledge_list_docs_filters_by_mine(monkeypatch):
    """只看自己建的资料要落到 created_by，并把 is_mine 算好回给前端。"""
    mod = _knowledge()
    monkeypatch.setattr(mod, "_is_manager", lambda user, db: False)
    monkeypatch.setattr(mod, "_visibility", lambda db, user, manage: ("1=1", {}))
    monkeypatch.setattr(mod, "_safe_scalar", lambda *a, **k: 0)

    captured = {}

    def fake_rows(db, sql, **kw):
        captured["sql"] = sql
        captured["args"] = kw
        return [{"id": 1, "title": "换模 SOP", "created_by": 7},
                {"id": 2, "title": "别人的", "created_by": 9}]

    monkeypatch.setattr(mod, "_safe_rows", fake_rows)
    db, user = MagicMock(), MagicMock(id=7)

    out = mod.list_docs(q=None, scope=None, sort=None, vectorized=None,
                        source=None, mine=1, page=1, page_size=20, db=db, user=user)
    assert "AND d.created_by = :me" in captured["sql"]
    assert captured["args"]["me"] == 7
    items = out["data"]["items"]
    assert [it["is_mine"] for it in items] == [True, False]
    assert out["data"]["mine"] == 1

    mod.list_docs(q=None, scope=None, sort=None, vectorized=None,
                  source=None, mine=None, page=1, page_size=20, db=db, user=user)
    where = captured["sql"].split(" WHERE ", 1)[1].split(" ORDER BY ", 1)[0]
    assert "created_by" not in where


def test_knowledge_doc_detail_flags_can_edit(monkeypatch):
    """详情要区分「我建的」和「有管理权」：前者给编辑，后者也给。"""
    mod = _knowledge()
    monkeypatch.setattr(mod, "_visibility", lambda db, user, manage: ("1=1", {}))
    monkeypatch.setattr(mod, "_safe_rows", lambda *a, **k: [{"id": 5, "title": "T", "created_by": 7}])
    db = MagicMock()

    monkeypatch.setattr(mod, "_is_manager", lambda user, db: False)
    out = mod.doc_detail(5, db=db, user=MagicMock(id=7))
    assert out["data"]["is_mine"] is True
    assert out["data"]["can_edit"] is True

    out = mod.doc_detail(5, db=db, user=MagicMock(id=42))
    assert out["data"]["is_mine"] is False
    assert out["data"]["can_edit"] is False

    monkeypatch.setattr(mod, "_is_manager", lambda user, db: True)
    out = mod.doc_detail(5, db=db, user=MagicMock(id=42))
    assert out["data"]["can_edit"] is True


def test_h5_ai_contract_covers_batch18_capabilities():
    """资料的新建/编辑闭环，后端接口、前端封装、页面、三语键都要齐。"""
    ai = AI_TS.read_text(encoding="utf-8")
    for marker in ("export function createKnowledgeDoc(", "export function updateKnowledgeDoc(",
                   "mine?: number", "is_mine?: boolean", "can_edit?: boolean"):
        assert marker in ai, f"api/ai.ts 缺 {marker}"

    docs = (REPO / "frontend-h5/src/pages/AiDocsPage.vue").read_text(encoding="utf-8")
    for marker in ("const mineOnly = ref(false)", "mine: mineOnly.value ? 1 : undefined",
                   "async function saveDoc(", "function openCreate(",
                   "function openEdit(", '@click="pickMine"', 'v-model:show="editOpen"',
                   "detail?.can_edit", "d.is_mine"):
        assert marker in docs, f"资料页缺少新建/编辑闭环: {marker}"

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("docsCreate", "docsEdit", "docsMineOnly", "docsMine",
                    "docsEditVectorize", "docsSavedVectorized"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"


def test_h5_ai_contract_covers_batch19_capabilities():
    """助手能力清单与委托会话回看，前后端都要真的接上。"""
    ai = AI_TS.read_text(encoding="utf-8")
    for marker in ("export function listAgentTools(", "export function listEmployeeConversations(",
                   "export function getEmployeeConversation(", "export function deleteEmployeeConversation("):
        assert marker in ai, f"api/ai.ts 缺 {marker}"

    assist = (REPO / "frontend-h5/src/pages/AiAssistantPage.vue").read_text(encoding="utf-8")
    for marker in ("listAgentTools,", "async function openTools(",
                   "const availableTools = computed(", '@click="openTools"',
                   'v-model:show="toolsOpen"'):
        assert marker in assist, f"助手页缺少能力清单: {marker}"

    emp = (REPO / "frontend-h5/src/pages/AiEmployeesPage.vue").read_text(encoding="utf-8")
    for marker in ("listEmployeeConversations,", "async function loadConversations(",
                   "async function openConvDetail(", "async function removeConv(",
                   '@click="openConversations"', 'v-model:show="convOpen"',
                   'v-model:show="convDetailOpen"'):
        assert marker in emp, f"数字员工页缺少委托会话: {marker}"

    for loc in ("zh-CN", "en-US", "ko-KR"):
        pack = (REPO / f"frontend-h5/src/locales/{loc}.ts").read_text(encoding="utf-8")
        for key in ("agentToolsTitle", "agentToolsCount", "empConversations",
                    "empConvDeleteConfirm", "empConvNotFound"):
            assert f"{key}:" in pack, f"{loc} 缺 {key}"
