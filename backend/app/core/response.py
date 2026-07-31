from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = ""
    data: Optional[T] = None


def ok(data: Any = None, msg: str = "") -> dict:
    return {"code": 200, "msg": msg, "data": data}


def fail(code: int, msg: str, data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}

