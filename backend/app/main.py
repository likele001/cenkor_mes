from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.errors import BizError
from app.core.response import fail, ok
from app.crud.rbac import ensure_permissions, create_default_roles
from app.crud.user import create_user
from app.models.base import Base
from app.models.user import User


app = FastAPI(title=settings.APP_NAME)
app.include_router(api_router, prefix="/api")


@app.get("/api/health")
def health():
    return ok({"status": "ok", "build": "20260727-cenkormes"})


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=200, content=fail(exc.status_code, str(exc.detail)), headers=exc.headers)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=200, content=fail(400, "参数校验失败", {"errors": exc.errors()}))


@app.exception_handler(BizError)
def biz_exception_handler(_: Request, exc: BizError):
    return JSONResponse(status_code=200, content=fail(exc.code, exc.msg))


logger = logging.getLogger("uvicorn.error")


@app.exception_handler(Exception)
def any_exception_handler(_: Request, exc: Exception):
    logger.error("未捕获异常: %s", exc, exc_info=exc)
    if settings.APP_ENV == "dev":
        return JSONResponse(
            status_code=200,
            content=fail(
                500,
                "服务器错误",
                {"error": str(exc), "type": type(exc).__name__},
            ),
        )
    return JSONResponse(status_code=200, content=fail(500, "服务器错误"))


@app.on_event("startup")
def on_startup():
    if settings.DB_AUTO_CREATE:
        Base.metadata.create_all(bind=engine)
    if settings.DB_AUTO_SEED:
        db: Session = SessionLocal()
        try:
            ensure_permissions(db)
            create_default_roles(db)

            # 创建默认管理员账号
            admin = db.scalar(select(User).where(User.username == "admin"))
            if not admin:
                from app.models.role import Role
                admin_role = db.scalar(select(Role).where(Role.code == "admin"))
                admin = create_user(db, "admin", "admin123", full_name="系统管理员", is_superuser=True)
                if admin_role:
                    admin.roles = [admin_role]
                logger.info("已创建默认管理员账号: admin / admin123")

            db.commit()
        finally:
            db.close()

    # 系统版本表种子（幂等，从 CHANGELOG.json 同步，仅在版本号不存在时插入）
    try:
        from pathlib import Path
        from app.crud.system_version import sync_changelog_from_file
        db = SessionLocal()
        try:
            changelog_path = Path(__file__).resolve().parents[1] / "CHANGELOG.json"
            added = sync_changelog_from_file(db, changelog_path)
            if added:
                logger.info("synced %d system versions from CHANGELOG.json", added)
        finally:
            db.close()
    except Exception as e:
        logger.warning("seed system versions failed: %s", e)

