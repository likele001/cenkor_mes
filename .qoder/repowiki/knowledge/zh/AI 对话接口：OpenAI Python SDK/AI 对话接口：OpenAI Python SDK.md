---
kind: external_dependency
name: AI 对话接口：OpenAI Python SDK
slug: openai-api
category: external_dependency
category_hints:
    - vendor_identity
    - auth_protocol
scope:
    - '**'
---

### 身份与角色

### 集成点
- 路由：`backend/app/api/ai_compat/` 目录。

### 稳定用法
- 需要配置 OpenAI API Key 及 base URL（若走兼容网关）；具体参数需对照 `openai` SDK v1 官方文档确认。