# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
import logging
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.errors import BizError
from app.core.middleware import SecurityHeadersMiddleware
from app.core.observability import RequestContextMiddleware, enable_slow_query_logging, setup_logging
from app.core.response import fail, ok
from app.core.security import ensure_secure_jwt_secret
from app.crud.rbac import ensure_permissions, create_default_roles
from app.crud.tenant import ensure_default_tenant
from app.crud.user import create_user
from app.extension_host import mount_all, startup_host
from app.models.base import Base
from app.models.user import User
# 导入即注册 Session 级监听：看板相关表 commit 后推 WebSocket 刷新
from app.services import dashboard_events as _dashboard_events  # noqa: F401


app = FastAPI(title=settings.APP_NAME)

# 安全响应头：全局补发，不覆盖已有值
app.add_middleware(SecurityHeadersMiddleware)

# CORS：仅当显式配置了 CORS_ORIGINS（逗号分隔）时才启用白名单
if settings.CORS_ORIGINS:
    _allowed = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Host 头校验：仅当显式配置了 TRUSTED_HOSTS 时才启用
if settings.TRUSTED_HOSTS:
    _hosts = [h.strip() for h in settings.TRUSTED_HOSTS.split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

# 可观测性（PERF-1）：结构化访问日志 + request_id 关联 + SQLAlchemy 慢查询日志。
# RequestContextMiddleware 最后注册 = 最外层，可统计含 CORS/安全头在内的完整耗时。
setup_logging()
enable_slow_query_logging(engine)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router, prefix="/api")

# 扩展宿主：扫描 backend/extensions/ 并挂载 /api/extensions/{key} 路由。
# 零管理界面——应用目录/发卡/绑定/吊销全部在独立应用中心完成。
mount_all(app)


_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


@app.get("/api/health")
def health():
    version = _read_version()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - 健康检查必须给出结果而不是抛 500
        logging.getLogger("uvicorn.error").warning("health.db_check_failed: %s", exc)
        db_ok = False
    data = {"status": "ok" if db_ok else "degraded", "db": "up" if db_ok else "down",
            "build": version, "version": version}
    if not db_ok:
        return JSONResponse(status_code=503, content=ok(data))
    return ok(data)


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


def _ensure_default_admin(db: Session) -> None:
    """创建默认管理员：dev 用内置口令，其他环境必须显式配置 ADMIN_INIT_PASSWORD。"""
    if db.scalar(select(User).where(User.username == "admin")):
        return
    if settings.APP_ENV == "dev":
        init_password = "admin123"
    else:
        init_password = (settings.ADMIN_INIT_PASSWORD or "").strip()
    if not init_password or len(init_password) < settings.PASSWORD_MIN_LENGTH:
        logger.warning(
            "未创建默认管理员：APP_ENV=%s 时请设置 ADMIN_INIT_PASSWORD（至少 %d 位）",
            settings.APP_ENV,
            settings.PASSWORD_MIN_LENGTH,
        )
        return
    from app.models.role import Role
    admin_role = db.scalar(select(Role).where(Role.code == "admin"))
    admin = create_user(db, "admin", init_password, full_name="系统管理员", is_superuser=True)
    if admin_role:
        admin.roles = [admin_role]
    if settings.APP_ENV == "dev":
        logger.info("已创建默认管理员账号: admin / admin123")
    else:
        logger.info("已创建默认管理员账号: admin（口令来自 ADMIN_INIT_PASSWORD）")


@app.on_event("startup")
def on_startup():
    ensure_secure_jwt_secret()
    if settings.DB_AUTO_CREATE:
        if settings.APP_ENV != "dev":
            logger.warning(
                "DB_AUTO_CREATE=true（APP_ENV=%s）：启动时执行 DDL；生产环境建议关闭并改用 alembic upgrade head",
                settings.APP_ENV,
            )
        Base.metadata.create_all(bind=engine)
    if settings.DB_AUTO_SEED:
        db: Session = SessionLocal()
        try:
            if ensure_default_tenant(db):
                logger.info("已创建默认租户 tenant_id=1")

            ensure_permissions(db)
            create_default_roles(db)
            _ensure_default_admin(db)

            # 定时任务默认配置（幂等：已存在的按 name 跳过）
            from app.services.cron_job_seeder import seed_default_cron_jobs
            added_cron = seed_default_cron_jobs(db)
            if added_cron:
                logger.info("已初始化 %d 个系统定时任务", added_cron)

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

    # 在线升级：若上次升级在重启阶段被中断，按守护脚本结果回填任务最终状态
    try:
        from app.services import upgrade_service
        db = SessionLocal()
        try:
            upgrade_service.reconcile_restarts(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning("reconcile upgrade jobs failed: %s", e)

    # 扩展宿主启动：执行扩展迁移 + 注入权限点 + 启动授权同步线程（异常不阻塞主流程）
    try:
        startup_host()
    except Exception as e:
        logger.warning("extension host startup failed: %s", e)


@app.on_event("shutdown")
def on_shutdown():
    # 扩展事件总线线程池停止（不等待在飞 handler：通知型尽力而为）
    try:
        from app.extension_host.events import event_bus

        event_bus.shutdown(wait=False)
    except Exception as e:
        logger.warning("extension event bus shutdown failed: %s", e)

