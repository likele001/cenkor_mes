---
kind: external_dependency
name: 关系型数据库：MySQL 8（PyMySQL 驱动）
slug: mysql-8
category: external_dependency
scope:
    - '**'
---

### 身份与角色
- 主数据源为 MySQL 8，使用 SQLAlchemy 2.x + PyMySQL 驱动（URL scheme `mysql+pymysql`，字符集 `utf8mb4`）。
- Alembic 负责迁移（`backend/alembic/`），默认启动时自动建表并填充种子数据（`DB_AUTO_CREATE` / `DB_AUTO_SEED`）。

### 集成点
- 配置：`backend/app/core/config.py` 的 `DB_URL`、`DB_ECHO`、`DB_AUTO_CREATE`、`DB_AUTO_SEED`。
- ORM 层：`backend/app/models/` 下各业务模型，CRUD 在 `backend/app/crud/`，API 路由在 `backend/app/api/`。

### 稳定用法
- 新表需先写 Alembic migration（`backend/alembic/versions/`），再在 models 中定义对应 SQLAlchemy 模型。