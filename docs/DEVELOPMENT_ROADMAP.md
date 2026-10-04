# CenkorMES 开发路线图（可行性方案）

> 版本：v1.0 草案 ｜ 生成日期：2026-10-04
> 范围：本轮"继续完善"聚焦三大方向 —— **云存储落地 / 测试与质量加固 / 性能与可观测性**
> 定位：决策完整的落地计划，含现状盘点、阶段拆分、优先级、工时、验收与风险。

---

## 0. 现状盘点（基于代码核实，非文档臆测）

| 维度 | 事实 | 结论 |
|---|---|---|
| 云存储 | `app/storage/factory.py` 中 `get_active_storage/build_storage/get_storage_for` **全部写死 `return LocalStorage()`**；`.env` 的 OSS/COS/七牛 凭据为空壳 | 重大缺口，但已有完整蓝图 + 源仓可参考 |
| 依赖 | `requirements.txt` 已含 `oss2`、`cos-python-sdk-v5`、`qiniu`、`cryptography` | 落地无需重型新增依赖 |
| 源参考 | `/www/wwwroot/cenkor-admin/.../apps/cloud_storage/`（crypto/models/drivers/router） | 可移植，但需 **async→sync、S3→原生 SDK** 适配 |
| 测试 | 后端 **13** 个测试文件 vs **108** 个 API 路由模块；Alembic 仅 **4** 个迁移 | 覆盖薄弱、schema 演进靠自动建表 |
| 前端 | 管理后台 87 页、H5 22 页；Element Plus 单块 779kB（gzip 248kB） | 功能成熟；有分包/性能优化空间 |
| 可观测性 | 仅标准库 logging，无指标/慢查询/链路 | 生产排障靠日志翻找 |

---

## 1. 方向一：云存储落地（P0，预计 5–6 人日）

### 目标
让 MES 具备**多云统一接入 + 后台热切换 + 凭据加密入库 + 前端签名直传**，消除"后端中转所有文件流量"的带宽与单点压力。

### 阶段拆分

| 阶段 | 任务 | 产出 | 工时 | 状态 |
|---|---|---|---|---|
| **CS-1** | 凭据 AES-256-GCM 加密模块 + `factory` 去写死（驱动注册表 + 向后兼容降级） | `app/storage/crypto.py`、重构 `factory.py`、单元测试 | 0.5d | ✅ 本轮完成 |
| **CS-2** | `CloudStorageConfig` 模型 + Alembic 迁移 + 配置 CRUD（凭据密文入库、读取脱敏） | `models/cloud_storage.py`、`alembic/versions/0005_*`、`services/cloud_storage_config.py` | 1d | ⏳ |
| **CS-3** | 真实云驱动（实现现有 `Storage` 协议）：阿里 OSS / 腾讯 COS / 七牛 Kodo | `app/storage/drivers/{aliyun,cos,qiniu}.py` + 注册 | 1.5d | ⏳ |
| **CS-4** | 管理端 API `/admin/cloud-storage/*`：config 读写、activate 热切换、health 连通性、presign 直传 + 权限点 | `api/admin/cloud_storage.py`、`seed.py` 加 `cloud_storage.manage` | 1d | ⏳ |
| **CS-5** | 前端"系统设置→云存储"页面 + 菜单 + i18n | `pages/system/CloudStoragePage.vue` | 0.5d | ⏳ |
| **CS-6** | 历史附件迁移任务（本地→云，带进度/失败重试，P1） | 迁移任务 + 状态查询 | 1d | ⏳ |

### 关键设计决策
1. **接口对齐现有 `Storage` 协议（sync）**，不照搬 cenkor-admin 的 async S3 协议 —— 与 MES 全栈 sync 风格一致，改造面最小。
2. **凭据密钥派生自 `JWT_SECRET`**（`key = SHA256(JWT_SECRET)`），不引入独立密钥体系；支持 `JWT_SECRET_OLD` 轮换回退。
3. **向后兼容降级**：CS-1 阶段未注册的云驱动降级为 `local` 并告警，**绝不因 `.env` 里历史空壳配置导致上传中断**。
4. **附件读取按 `attachment.storage_driver` 选驱动**，兼容期本地与云端双读（详见蓝图 §4.3）。

### 验收标准
- 后台切换 provider 后**不重启**即对新上传生效；`storage_driver` 落库正确。
- DB 中凭据为密文，API 读取返回脱敏值（`AKI••••7890`）。
- H5/小程序 `presign` 拿到临时 PUT URL 直传成功、列表可查。
- `pytest` 覆盖 crypto 往返/轮换/防篡改 + factory 选择与降级。

### 风险
| 风险 | 缓解 |
|---|---|
| `JWT_SECRET` 变更后历史凭据解密失败 | 部署文档明确"上线后禁改 JWT_SECRET"；提供凭据重录 UI |
| 云 endpoint 配置错误难定位 | `health` 接口做连通性校验，前端展示可读错误 |
| 原生 SDK 与 async 源仓差异 | 按现有 sync `Storage` 协议重写，不搬运 async 代码 |

---

## 2. 方向二：测试与质量加固（P0/P1，预计 4–5 人日）

### 现状
13 测试文件 / 108 路由；核心闭环（订单→工单→派工→报工→审核→算薪）缺端到端回归；迁移脚本仅 4 个，schema 变更靠 `create_all`，升级不可控。

### 阶段拆分
| 阶段 | 任务 | 工时 |
|---|---|---|
| **QA-1** | 测试脚手架：统一 SQLite/事务回滚 fixtures、`pytest-cov` 覆盖率门槛（核心域 ≥60%） | 0.5d |
| **QA-2** | 核心闭环集成测试：order→workorder→dispatch→report→audit→salary 全链路 + 自动算薪边界 | 1.5d |
| **QA-3** | 安全/RBAC 回归：越权访问、`require_permissions`、JWT 强校验、上传 MIME/XSS 检测 | 1d |
| **QA-4** | Alembic 迁移规范化：`--autogenerate` + 人工评审，补齐历史缺表迁移，`upgrade/downgrade` CI 校验 | 1d |
| **QA-5** | CI 门禁：后端 `pytest` + 前端 `vue-tsc -b && vite build` + `eslint`（GitHub Actions） | 0.5d |

### 验收
- 关键路径有回归测试；PR 触发 CI，红则不可合并。
- `alembic upgrade head` 在空库/存量库均可幂等执行。

---

## 3. 方向三：性能与可观测性（P1，预计 4 人日）

### 阶段拆分
| 阶段 | 任务 | 工时 |
|---|---|---|
| **PERF-1** | 结构化请求日志 + SQLAlchemy 慢查询日志（阈值可配）；可选 `/metrics`（prometheus-fastapi-instrumentator） | 1d |
| **PERF-2** | 热点表索引审计（work_order/task/report/salary 外键+状态+日期）；列表接口强制分页；N+1 排查（`selectinload`） | 1.5d |
| **PERF-3** | Redis 缓存：`public-config`、字典、看板聚合结果 + 失效策略 | 0.5d |
| **PERF-4** | 前端：路由级分包审计、Element Plus 用 `advancedChunks` 安全拆分（避免本轮白屏那类跨 chunk 循环）、CI 产物体积预算 | 1d |

### 验收
- 看板/列表首屏接口 P95 明显下降；无 N+1 慢查询。
- 生产可通过日志/指标定位慢请求；前端产物有体积预算护栏。

---

## 4. 建议排期（单人）

```
第 1 周：CS-1(✅) → CS-2 → CS-3        云存储打通真实上传
第 2 周：CS-4 → CS-5                    后台可配置 + 前端页
第 2 周并行：QA-1 → QA-2                测试脚手架 + 核心闭环回归
第 3 周：QA-3 → QA-4 → QA-5            安全/迁移/CI 门禁
第 3–4 周：PERF-1 → PERF-2 → PERF-3 → PERF-4   性能与可观测
第 4 周：CS-6（历史迁移，按需）
```

> 每完成一个可交付增量，按项目机制走 `scripts/release-all.sh` 登记版本并重启后端。

---

## 5. 本轮已交付（CS-1）
- `backend/app/storage/crypto.py`：AES-256-GCM 凭据加解密（密钥派生自 `JWT_SECRET`，支持轮换回退、脱敏）。
- `backend/app/storage/factory.py`：移除写死返回，改为**驱动注册表 + 配置解析 + 向后兼容降级**。
- `backend/tests/test_storage_crypto.py`：加密往返/随机 nonce/防篡改/脱敏 + 工厂选择与降级单测。

后续按 CS-2 起推进（需你确认继续）。
