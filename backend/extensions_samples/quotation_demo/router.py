# 演示扩展：报价单（后端路由）
# 挂载路径前缀：/api/extensions/quotation_demo/
# 依赖：挂载时自动附加登录鉴权 + 启用门控（未启用返回 403）
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.response import ok

router = APIRouter()


@router.get("/ping")
def ping():
    """扩展存活检查。"""
    return ok({"ok": True, "extension": "quotation_demo"})


@router.get("/quotes")
def list_quotes(db: Session = Depends(get_db)):
    """读取扩展自建表（由 migrations.sql 创建）。"""
    rows = db.execute(
        text("SELECT id, customer, amount, status FROM ext_quotation_demo ORDER BY id DESC LIMIT 50")
    ).mappings().all()
    return ok({"items": [dict(row) for row in rows]})
