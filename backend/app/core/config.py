# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "CenkorMES Backend"
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DB_URL: str = "mysql+pymysql://root:root@127.0.0.1:3306/cenkormes?charset=utf8mb4"
    DB_ECHO: bool = False
    DB_AUTO_CREATE: bool = True
    DB_AUTO_SEED: bool = True

    # 可观测性（PERF-1）
    HTTP_ACCESS_LOG: bool = True             # 是否输出结构化 HTTP 访问日志（含 request_id 与耗时）
    DB_SLOW_QUERY_MS: int = 800              # 慢查询阈值（毫秒），单次游标执行超过则 WARNING；<=0 关闭

    JWT_SECRET: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REMEMBER_ME_EXPIRE_MINUTES: int = 10080
    PUBLIC_BASE_URL: str = ""
    H5_PUBLIC_BASE_URL: str = ""

    # 安全基线
    JWT_SECRET_MIN_LENGTH: int = 32          # 生产环境 JWT 密钥最小长度
    PASSWORD_MIN_LENGTH: int = 6             # 用户密码最小长度（兼容内置种子账号长度）
    CORS_ORIGINS: str = ""                   # 允许跨域的来源，逗号分隔；留空则不开启 CORS
    TRUSTED_HOSTS: str = ""                  # 允许的 Host，逗号分隔；生产建议固定，留空不启用校验
    LOGIN_MAX_FAILURES: int = 10             # 登录失败锁定阈值（≤0 表示关闭限流）
    LOGIN_FAIL_WINDOW_SECONDS: int = 300     # 失败计数滑动窗口（秒）
    LOGIN_LOCKOUT_SECONDS: int = 300         # 锁定持续时间（秒）

    STORAGE_DRIVER: str = "local"
    STORAGE_LOCAL_ROOT: str = "./data/storage"
    FILE_MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    FILE_ALLOWED_MIME: str = (
        "image/jpeg,image/png,image/webp,application/pdf,"
        "video/mp4,video/quicktime,video/webm,video/3gpp,video/x-msvideo"
    )

    # 扩展宿主（MES 侧）：扩展加载机制。功能市场连接信息（hub 地址 / 实例令牌等）
    # 改由后台「功能市场」页写入 PlatformSetting，无需在此配置 .env
    EXTENSIONS_ENABLED: bool = True            # 扩展宿主总开关
    EXTENSIONS_DIR: str = "./extensions"       # 扩展安装目录（相对 backend/，也可用绝对路径）

    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/1"
    CELERY_TIMEZONE: str = "Asia/Shanghai"
    CELERY_ENABLE_UTC: bool = True


settings = Settings()
