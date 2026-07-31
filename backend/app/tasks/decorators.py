"""Celery task 公共装饰器 — 自动管理 DB session 生命周期"""
import functools
import logging
from collections.abc import Callable
from typing import Any

from app.core.db import SessionLocal

logger = logging.getLogger(__name__)


def db_task(func: Callable[..., Any]) -> Callable[..., Any]:
    """装饰器：为 Celery task 自动注入 db session 并在结束时 commit/close。

    使用方式：
        @shared_task(name="xxx")
        @db_task
        def my_task(db, ...):
            ...  # db 已注入，无需手动 SessionLocal()

    - 未捕获异常时自动 rollback
    - 正常返回时自动 commit（若 task 内已 commit 也无副作用）
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        db = SessionLocal()
        try:
            result = func(db, *args, **kwargs)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return wrapper
