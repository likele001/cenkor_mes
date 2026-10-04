---
kind: configuration_system
name: 后端 Pydantic Settings + .env 配置系统与前端 Vite 环境变量
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/core/config.py
    - backend/.env
    - backend/.env.example
    - backend/main.py
    - backend/app/core/db.py
    - backend/app/core/redis_client.py
    - backend/app/storage/config.py
    - backend/alembic/env.py
    - frontend-admin-pro/.env.development
    - lightmes-miniapp/.env.production
---

## 1. 总体方案

CenkorMES 的配置系统采用 **Pydantic v2 `pydantic_settings.BaseSettings`** 作为唯一运行时配置入口，配合 `.env` 文件与环境变量注入；前端（admin-pro、h5、miniapp）使用 Vite 的 `VITE_*` 前缀环境变量。配置按“应用级常量 + 外部化参数”分层：应用名、端口、JWT、数据库、Redis、Celery、存储驱动等全部通过 `backend/app/core/config.py` 中的 `Settings` 模型集中声明。

## 2. 核心文件与包

- `backend/app/core/config.py` — 定义 `Settings(BaseSettings)`，暴露模块级单例 `settings`。
- `backend/.env` / `backend/.env.example` — 实际运行配置与模板。
- `backend/main.py` — uvicorn 启动入口，读取 `APP_HOST`/`APP_PORT`/`APP_ENV`。
- `backend/app/core/db.py` — 基于 `settings.DB_URL` 创建 SQLAlchemy engine/session。
- `backend/app/core/redis_client.py` — 基于 `settings.REDIS_URL` 懒加载 Redis 客户端，连接失败时降级为 None。
- `backend/app/storage/config.py` — 云存储驱动的 dataclass 配置结构（Aliyun OSS / Tencent COS / Qiniu Kodo）。
- `frontend-admin-pro/.env.development` — `VITE_API_BASE=/api`。
- `lightmes-miniapp/.env.production` — `VITE_API_BASE_URL=https://ck.mes.cenkor.cn/api`。
- `docker-compose.yml` / `docker/scripts/*` — 容器编排中通过环境变量覆盖 `.env`。

## 3. 架构与约定

### 3.1 加载顺序与来源

`Settings.model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")` 表明：
- 默认从项目根目录的 `.env` 读取键值对。
- 未声明的额外字段被忽略（`extra="ignore"`），而非报错。
- 所有字段均有默认值，因此即使 `.env` 缺失也能以开发默认值启动。

配置优先级遵循 pydantic-settings 规范：进程环境变量 > `.env` 文件 > 代码默认值。例如当前 `.env` 覆盖了 `DB_URL`、`REDIS_URL`、`CELERY_*`、`PUBLIC_BASE_URL`、`H5_PUBLIC_BASE_URL` 等，而 `JWT_SECRET`、`STORAGE_DRIVER` 等仍走代码默认值或 `.env.example` 中的注释说明。

### 3.2 配置分组

| 分组 | 关键字段 | 用途 |
|---|---|---|
| 应用 | `APP_NAME`, `APP_ENV`, `APP_HOST`, `APP_PORT` | uvicorn 启动参数 |
| 数据库 | `DB_URL`, `DB_ECHO`, `DB_AUTO_CREATE`, `DB_AUTO_SEED` | SQLAlchemy 引擎与初始化开关 |
| 认证 | `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REMEMBER_ME_EXPIRE_MINUTES` | JWT 签发与过期 |
| 安全基线 | `JWT_SECRET_MIN_LENGTH`, `PASSWORD_MIN_LENGTH`, `CORS_ORIGINS`, `TRUSTED_HOSTS`, `LOGIN_MAX_FAILURES`, `LOGIN_FAIL_WINDOW_SECONDS`, `LOGIN_LOCKOUT_SECONDS` | 密码策略、CORS、Host 校验、登录限流 |
| 文件存储 | `STORAGE_DRIVER`, `STORAGE_LOCAL_ROOT`, `FILE_MAX_UPLOAD_SIZE`, `FILE_ALLOWED_MIME` | 本地/云存储驱动选择与 MIME 白名单 |
| 缓存/任务 | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TIMEZONE`, `CELERY_ENABLE_UTC` | Redis 与 Celery 连接 |
| 前端 URL | `PUBLIC_BASE_URL`, `H5_PUBLIC_BASE_URL` | 公开页面与 H5 基础地址 |
| 云存储 | `ALIYUN_OSS_*`, `TENCENT_COS_*`, `QINIU_KODO_*` | 各云厂商 endpoint/bucket/key |
| 小程序 | `WX_MINIAPP_APPID`, `WX_MINIAPP_SECRET` | 微信登录凭据 |

### 3.3 消费方式

- 全局单例：`from app.core.config import settings`，在 API、Alembic、服务层直接读属性（如 `settings.DB_URL`、`settings.FILE_MAX_UPLOAD_SIZE`、`settings.REDIS_URL`）。
- Alembic 迁移：`alembic/env.py` 通过 `config.set_main_option("sqlalchemy.url", settings.DB_URL)` 复用同一份 DB URL。
- 数据库连接：`app/core/db.py` 用 `create_engine(settings.DB_URL, echo=settings.DB_ECHO, pool_pre_ping=True, pool_recycle=3600)`。
- Redis 连接：`get_redis()` 懒加载并缓存，首次 ping 失败后标记 `_client=False` 返回 None，供验证码等能力降级到内存实现。
- 存储驱动：`app/storage/config.py` 用 frozen dataclass 描述云厂商配置，由上层 factory 根据 `STORAGE_DRIVER` 选择具体实现。

### 3.4 前端配置

- admin-pro：`.env.development` 仅设 `VITE_API_BASE=/api`，构建期被 Vite 注入到 `import.meta.env.VITE_API_BASE`。
- miniapp：`.env.production` 设置 `VITE_API_BASE_URL=https://ck.mes.cenkor.cn/api`，注释说明管理端与小程序共用同一 Nginx 反向代理到 FastAPI。
- h5：无独立 `.env.*`，API 地址由运行时动态决定（见 `src/utils/http.ts` 等）。 

## 4. 约定与约束

- **单一配置源**：后端所有运行时配置统一经 `app.core.config.Settings` 暴露，业务模块不得自行解析 `.env` 或硬编码连接串。
- **敏感信息不入库**：`JWT_SECRET`、`DB_URL`、云存储 AK/SK、小程序 AppID/Secret 等仅存在于 `.env` 或环境变量中，不在代码库提交（`.gitignore` 排除 `*.env`）。
- **生产环境强制项**：`JWT_SECRET_MIN_LENGTH=32` 与 `PASSWORD_MIN_LENGTH=6` 在 `Settings` 中以默认值声明，配合 `app/core/security.py` 中的校验逻辑（测试 `test_security.py`、`test_security_p4.py` 覆盖）——这是仓库内唯一对配置值施加长度约束的地方。
- **CORS/Host 校验可选**：`CORS_ORIGINS` 与 `TRUSTED_HOSTS` 留空表示关闭对应检查，生产部署文档建议显式固定 Host。
- **Redis 可降级**：`redis_client.get_redis()` 捕获异常后将 `_client` 置为 `False` 并返回 `None`，调用方需判空（如验证码、推送监控），否则不会因 Redis 不可用导致启动失败。
- **文件上传大小与 MIME 白名单**：`FILE_MAX_UPLOAD_SIZE` 与 `FILE_ALLOWED_MIME` 在多个上传接口中被重复读取（`v1/files.py`、`admin/system/attachments.py`、`admin/system/print_templates.py`、`admin/production/tasks.py`、`admin/production/orders.py`），是统一的上传限制入口。
- **云存储配置结构化**：OSS/COS/Kodo 三套凭据以 `CloudDriverConfig(endpoint, region, bucket, access_key, secret_key, custom_domain)` 数据类承载，新增云厂商需在 `storage/config.py` 与 `storage/factory.py` 同步扩展。
- **前端 API 地址隔离**：每个前端子项目通过独立的 `.env.*` 文件指定 `VITE_API_BASE[_URL]`，避免多端共享同一构建产物。

## 5. 已知缺口

- `.env.example` 中存在 `CRM_PUBLIC_POOL_RECYCLE_HOUR/MINUTE` 等字段，但 `Settings` 模型未声明，会被 `extra="ignore"` 静默丢弃——这些键目前可能仅在业务代码中通过 `os.environ` 或其他方式读取（未在搜索结果中出现），属于配置与模型不同步的风险点。
- 前端 admin-pro 与 h5 缺少 `.env.production` 示例，生产构建时的 API 地址依赖宿主环境或 CI 注入。