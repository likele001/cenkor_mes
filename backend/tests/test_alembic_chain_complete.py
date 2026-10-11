# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""§4：`alembic upgrade head` 必须能单独建出完整库

0001 的建表动作是 `Base.metadata.create_all`，所以「链能不能建全」取决于
1) 模型模块有没有被注册进 metadata，2) 后续版本会不会和它撞车。
这两点在只有 MySQL 可跑的时候都是隐性的：本用例把整条链在临时 SQLite 上
从空库跑一遍，直接断言结果覆盖全部模型表。

ALEMBIC_DB_URL 由 alembic/env.py 读取，未设置时才回落到 settings.DB_URL，
所以这个测试不会碰真实数据库。
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]

# 历史遗留：这些表只在老库里存在，模型已删除，链也不建（无代码引用）。
# platform_ai_* 三张已从"遗留"里移出 —— 0014 起它们是链内的正式表。
_LEGACY_ONLY = {
    "ai_alert_events",
    "ai_conversations",
    "ai_messages",
    "dingtalk_push_logs",
    "wecom_push_logs",
}


def _all_model_tables() -> set[str]:
    from app.models.base import Base

    import app.models as _pkg
    for mod in pkgutil.iter_modules(_pkg.__path__):
        importlib.import_module(f"app.models.{mod.name}")
    from app.integration.crm_adapter import models as _crm  # noqa: F401

    return set(Base.metadata.tables)


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    """空库 → alembic upgrade head，返回（engine, 表集合）。"""
    db_path = tmp_path_factory.mktemp("alembic") / "chain.db"
    env = {**os.environ, "ALEMBIC_DB_URL": f"sqlite:///{db_path}"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"迁移链在空库上跑不通：\n{proc.stderr[-4000:]}"
    assert "Traceback" not in proc.stderr, proc.stderr[-4000:]

    eng = create_engine(f"sqlite:///{db_path}")
    return eng, set(inspect(eng).get_table_names())


def test_chain_builds_every_model_table(migrated_db):
    _eng, built = migrated_db
    missing = sorted(_all_model_tables() - built - _LEGACY_ONLY)
    assert not missing, f"这些模型表没有对应的迁移，新库建不出来：{missing}"


def test_chain_leaves_nothing_for_create_all_to_add(migrated_db):
    """链建完之后再跑 create_all，不该有任何新表——
    这正是关掉 DB_AUTO_CREATE 的前提。"""
    from app.models.base import Base

    eng, built = migrated_db
    before = set(built)
    Base.metadata.create_all(bind=eng, checkfirst=True)
    extra = set(inspect(eng).get_table_names()) - before
    assert not extra, f"启动期 create_all 还会补建这些表，说明迁移链缺内容：{sorted(extra)}"


def test_migration_history_is_linear():
    """单线历史：分叉后 `upgrade head` 会直接报 MultipleHeads。

    断言「只有一个 head」而不是「head 叫什么」——版本号会随每条新迁移往前挪，
    钉死名字只会逼得人每加一条迁移就回来改测试。
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"迁移链分叉了（upgrade head 会报 MultipleHeads）：{heads}"

    walked = {rev.revision for rev in script.walk_revisions()}
    assert "0013_orphan_model_tables" in walked, "0013 补的孤儿表建表语句不在链上了"


def test_orphan_tables_are_not_referenced_by_code(migrated_db):
    """链不建的这几张遗留表，代码里也不能有人查——否则新库一上来就 no such table。"""
    app_dir = BACKEND / "app"
    hits: list[str] = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text(errors="ignore")
        for table in _LEGACY_ONLY:
            if f'"{table}' in text or f"'{table}" in text:
                hits.append(f"{table}:{path.relative_to(BACKEND)}")
    assert not hits, f"这些表不在迁移链里却被代码引用：{hits}"
