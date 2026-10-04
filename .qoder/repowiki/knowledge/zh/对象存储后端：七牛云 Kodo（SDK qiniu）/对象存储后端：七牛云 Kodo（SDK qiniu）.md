---
kind: external_dependency
name: 对象存储后端：七牛云 Kodo（SDK qiniu）
slug: qiniu-kodo
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- 云厂商：七牛云对象存储（Kodo），通过 Python SDK `qiniu` 接入。
- 作为第三个云存储备选后端，与 OSS/COS 共享同一 `CloudDriverConfig` 配置模型。

### 集成点
- 配置结构：`backend/app/storage/config.py` 的 `CloudDriverConfig` + `StorageConfig.qiniu`。
- 运行时入口：`backend/app/storage/factory.py`。

### 稳定用法
- 新增七牛实现时遵循 `app/storage/base.Storage` 抽象，并在 factory 中按 driver 路由。
- 部署凭据通过 endpoint、bucket、access_key、secret_key、custom_domain 注入；SDK 调用细节需对照 `qiniu` 官方文档确认。