---
kind: external_dependency
name: 对象存储后端：阿里云 OSS（SDK oss2）
slug: aliyun-oss
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 身份与角色
- 云厂商：阿里云对象存储（OSS），通过 Python SDK `oss2` 接入。
- 在 CenkorMES 中作为可插拔的对象存储后端之一，与腾讯云 COS、七牛云、本地磁盘并列；当前工厂默认返回 `LocalStorage`，但配置模型已预留 OSS/COS/七牛的 endpoint、region、bucket、access_key、secret_key、custom_domain。

### 集成点
- 配置结构：`backend/app/storage/config.py` 的 `CloudDriverConfig` + `StorageConfig.aliyun_oss` 字段定义了 OSS 所需的连接参数。

### 稳定用法
- 新增 OSS 实现时，应遵循现有 `app/storage/base.Storage` 抽象（save/delete/singed_url/resolve_path），并在 factory 中按 driver 路由到对应实现。
- 部署时需注入 endpoint、bucket、access_key、secret_key、custom_domain 等凭据；具体 SDK 调用细节需对照 `oss2` 官方文档确认。

### 注意
- 当前代码库中 OSS/COS/七牛的 SDK 虽已声明，但 storage factory 尚未真正落地这些后端（全部回退到 LocalStorage），属于预留能力。