---
kind: external_dependency
name: 对象存储后端：腾讯云 COS（SDK cos-python-sdk-v5）
slug: tencent-cos
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- 云厂商：腾讯云对象存储（COS），通过 Python SDK `cos-python-sdk-v5` 接入。
- 与阿里云 OSS、七牛云并列作为可插拔存储后端；当前默认仍为本地磁盘，但配置模型已预留其 endpoint、region、bucket、access_key、secret_key、custom_domain。

### 集成点
- 配置结构：`backend/app/storage/config.py` 的 `CloudDriverConfig` + `StorageConfig.tencent_cos`。
- 运行时入口：`backend/app/storage/factory.py` 的 storage 工厂方法。

### 稳定用法
- 新增 COS 实现时同样遵循 `app/storage/base.Storage` 抽象，并在 factory 中按 driver 路由。
- 部署凭据通过 endpoint、bucket、access_key、secret_key、custom_domain 注入；SDK 调用细节需对照 `cos-python-sdk-v5` 官方文档确认。