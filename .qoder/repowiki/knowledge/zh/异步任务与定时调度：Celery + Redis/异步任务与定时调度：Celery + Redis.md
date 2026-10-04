---
kind: external_dependency
name: 异步任务与定时调度：Celery + Redis
slug: celery-redis
category: external_dependency
category_hints:
    - framework_behavior
    - auth_protocol
scope:
    - '**'
---

### 身份与角色
- Celery 5.3+ 作为异步任务执行器，Redis 同时充当 Broker 与结果后端。
- 项目内包含两类任务：`app/tasks.py` 中的 Celery 任务（导出、通知、算薪等）以及 `app/schedulers/` 下的定时调度逻辑。

### 集成点
- 依赖：`celery[redis]`、`redis`。
- 配置：`backend/app/core/config.py` 中 `REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`、`CELERY_TIMEZONE=Asia/Shanghai`、`CELERY_ENABLE_UTC=True`。
- 应用入口：`backend/app/celery_app.py` 初始化 Celery app，`backend/app/tasks.py` 注册任务，`backend/app/schedulers/` 提供定时调度。

### 稳定用法
- 定时任务通过 schedulers 模块注册，时区固定为 `Asia/Shanghai`。
- 生产环境需确保 Redis 可达且 broker/result backend 分离（当前默认分别指向 Redis db 0 和 db 1）。