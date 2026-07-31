from app.storage.base import Storage, StoredObject
from app.storage.local import LocalStorage
from app.storage.factory import get_active_storage, get_storage_for, get_storage_backend, load_storage_config, build_storage

__all__ = [
    "Storage",
    "StoredObject",
    "LocalStorage",
    "get_active_storage",
    "get_storage_for",
    "get_storage_backend",
    "load_storage_config",
    "build_storage",
    "get_storage",
]


def get_storage() -> Storage:
    return LocalStorage()
