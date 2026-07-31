from typing import Any
from app.storage.local import LocalStorage
from app.storage.base import Storage


def get_storage_backend(driver: str = "local") -> Storage:
    return LocalStorage()


def get_active_storage(db: Any = None) -> Storage:
    return LocalStorage()


def get_storage_for(driver: str, db: Any = None) -> Storage:
    return LocalStorage()


def load_storage_config(db: Any = None) -> Any:
    from app.core.config import settings
    return type("Cfg", (), {"driver": settings.STORAGE_DRIVER})()


def build_storage(driver: str, cfg: Any = None) -> Storage:
    return LocalStorage()
