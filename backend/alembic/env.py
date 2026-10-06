# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from logging.config import fileConfig
import importlib
import os
import pkgutil

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.models import Base


def _register_all_models() -> None:
    """把 app/models 下所有模型模块导入一遍。

    create_all / --autogenerate 只看「已注册」的表：模型模块没被 import 时，
    它的表既不会被 migration 建出来，也不会出现在 autogenerate 的差异里，
    于是「加了模型忘了加迁移」可以无声存在很久。这里显式补齐。
    """
    import app.models as _models_pkg

    for mod in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"app.models.{mod.name}")
    # crm_adapter 的表不在 app/models 包里
    from app.integration.crm_adapter import models as _crm_models  # noqa: F401


_register_all_models()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ALEMBIC_DB_URL 只用于验证：迁移链可以在临时 SQLite 上跑一遍「从零建库」，
# 不必碰真实 MySQL。未设置时用应用自己的库。
config.set_main_option("sqlalchemy.url", os.getenv("ALEMBIC_DB_URL") or settings.DB_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

