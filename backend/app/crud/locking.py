# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""单据行锁助手：过账类操作先锁单据再校验状态，避免并发重复过账。

MySQL 下 ``refresh(with_for_update=True)`` 生成 ``SELECT ... FOR UPDATE``；
SQLite 测试库不支持该子句，SQLAlchemy 会忽略，所以单测只能覆盖状态校验，
并发语义需在 MySQL 上复核。
"""
from __future__ import annotations

from sqlalchemy.orm import Session


def lock_row(db: Session, model, pk: int):
    """按主键锁定一行并刷新列值；行不存在返回 None。"""
    obj = db.get(model, pk)
    if obj is None:
        return None
    db.refresh(obj, with_for_update=True)
    return obj
