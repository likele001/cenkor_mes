---
kind: logging_system
name: 后端日志系统 — Python 标准库 logging 零配置直用
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/main.py
    - backend/app/schedulers/database.py
    - backend/app/services/feishu/callbacks.py
    - backend/app/services/notify_dispatcher.py
    - backend/app/services/notify_guard.py
    - backend/app/services/notify_migration.py
    - backend/app/integration/crm_adapter/client.py
    - backend/app/integration/crm_adapter/router.py
    - backend/app/api/v1/files.py
    - backend/alembic/env.py
---

## 1. 使用的框架与工具

CenkorMES 后端没有引入第三方日志库（如 structlog、loguru、python-json-logger），也没有定义 `LOGGING` 字典或调用 `logging.config.dictConfig()`。整个后端统一使用 **Python 标准库 `logging`**，以“每个模块一个 logger”的方式直接 `import logging` 后通过 `logging.getLogger(__name__)` 获取实例。

- Alembic 迁移脚本在 `backend/alembic/env.py` 中仅通过 `fileConfig(config.config_file_name)` 加载 `alembic.ini` 中的 logging 配置，但仓库未提供 `alembic.ini` 的自定义 logging section，因此 Alembic 走的是默认 stderr 输出。
- 根目录存在空目录 `logs/`，但没有任何文件写入逻辑指向该目录；当前实现不会主动创建或滚动日志文件。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `backend/app/main.py` | FastAPI 应用入口，注册全局异常处理器，使用 `logging.getLogger("uvicorn.error")` 记录未捕获异常和启动期 seed 信息 |
| `backend/app/schedulers/database.py` | Celery Beat 数据库调度器，使用 `logger = logging.getLogger(__name__)` 记录 cron job 加载与 Redis 重载信号 |
| `backend/app/services/feishu/*.py` | 飞书集成回调、通知、欢迎消息等子模块，各自 `logger = logging.getLogger(__name__)` |
| `backend/app/services/notify_dispatcher.py` / `notify_guard.py` / `notify_migration.py` | 通知分发与守卫，同样按模块命名空间取 logger |
| `backend/app/integration/crm_adapter/client.py` & `router.py` | CRM 适配器，使用固定 logger 名称 `"crm_adapter"`（非 `__name__`） |
| `backend/app/api/v1/files.py` | 本地备份失败时 `logging.getLogger(__name__).warning(...)` |
| `backend/alembic/env.py` | 迁移入口，调用 `fileConfig` 继承 alembic.ini 的 logging 配置 |

## 3. 架构与约定

### 3.1 Logger 获取方式
绝大多数模块采用以下模式：
```python
import logging
logger = logging.getLogger(__name__)
```
这使每个 Python 包/模块拥有独立的命名空间 logger（如 `app.services.feishu.callbacks`、`app.schedulers.database`）。唯一例外是 `crm_adapter` 子模块显式使用固定名称 `"crm_adapter"`，以便集中过滤。

### 3.2 日志级别使用约定
代码中实际使用的级别如下：
- `logger.info`：业务正常事件（创建租户、同步版本、加载 cron job、CRM 状态回传成功等）
- `logger.warning`：可恢复异常或降级路径（飞书回调失败、通知入队失败、无收件人、CRM 未配置完整等）
- `logger.error`：明确错误（飞书 AI 调度失败、全局未捕获异常）
- `logger.exception`：在 `except` 块内记录带 traceback 的异常（cron job 加载失败、飞书卡片动作失败、迁移失败等）
- 未发现 `logger.debug` 的使用

### 3.3 结构化字段
日志输出为纯文本，参数化使用 `%s` 占位符（如 `logger.info("已创建默认管理员账号: admin / admin123")`），没有 JSON 结构化字段、trace_id、span_id、tenant_id 等上下文注入。请求级关联 ID、用户标识、租户标识并未自动附加到日志上下文中。

### 3.4 输出目标
- 应用运行时由 Uvicorn/Gunicorn 进程管理 stdout/stderr，Uvicorn 自身使用 `uvicorn.error` logger。
- 全局异常处理器 `any_exception_handler` 将未捕获异常写入 `uvicorn.error` logger，并附带 `exc_info=exc`。
- 没有配置 file handler、rotating handler 或外部日志收集（如 ELK、Fluent Bit）。

### 3.5 环境差异
`main.py` 的全局异常处理器根据 `settings.APP_ENV == "dev"` 决定是否返回详细错误体给前端，但日志本身始终记录 error 级别，不随环境切换输出级别。

## 4. 约定与约束

- **约定（观察到的模式）**：每个业务模块通过 `logging.getLogger(__name__)` 获取独立 logger，并以 `info/warning/error/exception` 四级区分日志严重性；CRM 适配器因跨模块共享而使用固定 logger 名 `"crm_adapter"`。
- **约束（有强制力的规则）**：仓库未提供任何 logging 配置文件（无 `logging.conf`、无 `dictConfig`、无 `alembic.ini` 的 logging section），因此所有日志行为完全依赖 Python `logging` 模块的默认 root handler（stderr），无法通过环境变量或配置文件调整输出格式、级别或目标。
- **约束（代码层面）**：Alembic 迁移入口 `env.py` 仅在 `config.config_file_name is not None` 时才调用 `fileConfig`，这意味着直接运行 `alembic upgrade head` 时不会加载任何自定义 logging 配置，迁移 SQL 与 Alembic 自身日志均走默认 stderr。
- **约束（作者指南）**：作者指南要求知识卡片聚焦后端业务模块与 FastAPI + MySQL + Celery 技术栈，本卡片仅描述后端日志实现，不涉及前端 Vue 应用的日志策略（前端未发现专用日志框架，主要使用浏览器 console）。

## 5. 总结

CenkorMES 的日志系统是**最小化的标准库 logging 直用方案**：无集中初始化、无结构化字段、无文件 sink、无 trace 上下文。日志主要用于运维排障与业务审计（租户创建、cron 调度、飞书回调、CRM 推送），若需生产级可观测性，需要在此基础上增加 structured logging（如 json formatter）、request context injection（trace_id、tenant_id、user_id）以及文件/远端 sink 配置。