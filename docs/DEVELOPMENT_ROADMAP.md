# CenkorMES 开发路线图（可行性方案）

> 版本：v2.0 ｜ 原稿 2026-10-04 ｜ **2026-11-06 按代码实际状态重新核实**
> 范围：云存储落地 / 测试与质量加固 / 性能与可观测性
>
> **核实方法**：逐项对照代码与测试文件，不采信旧文档的状态标记。
> 核实过程中两次发现「文档写待开发、代码其实已完成」（CS-6、PERF-1），
> 差点导致重复开发，因此本版**以代码为准**。

---

## 0. 现状盘点（2026-11-06 重新核实）

| 维度 | 事实 | 结论 |
|---|---|---|
| 云存储 | `crypto.py` / `factory.py` / 3 个云驱动（阿里 OSS、腾讯 COS、七牛 Kodo）/ 配置 API / 前端配置页 / 迁移任务与测试，全部在位 | **CS-1~CS-6 完成** |
| 历史附件迁移 | `services/cloud_storage_migration.py`（快照 id、sha256 校验、逐条提交）+ 15 项测试；v2.2.6 起结果区分 `done` / `partial` / `failed` | 完成 |
| 测试规模 | 后端 **56** 个测试文件、**624** 项用例；含核心闭环（`test_core_flow`、`test_api_integration_core_flow`、`test_closedloop_p4_salary`）与安全权限（5 个文件） | 已从原「13 文件」翻倍 |
| CI 门禁 | `.github/workflows/ci.yml`：后端 pytest + 双前端 `vue-tsc -b && vite build` | 完成 |
| 迁移链 | alembic **15** 个版本，CI 有 `test_alembic_chain_complete.py` 校验线性与 head | 完成 |
| 可观测性 | `core/observability.py`：request_id 日志中间件 + 慢查询日志（阈值 `DB_SLOW_QUERY_MS`，默认 800ms，`<=0` 关闭） | 完成（除 `/metrics`） |
| 索引 | **268** 个单列索引 + 关键复合索引（审批记录、订阅等） | 完成 |
| 业务缓存 | `core/business_cache.py`：版本化 key + Session 级 commit 失效；public-config、字典、看板 11 个聚合已接入（v2.2.10） | 完成 |
| 覆盖率门槛 | CI `ci.yml` 已带 `--cov-fail-under=50`（v2.2.7 起） | 完成 |
| 前端分包 | `vite.config.ts` 有 `manualChunks`；`element-plus` 779kB（gzip 248kB）仍偏大 | 完成，有优化空间 |

---

## 1. 方向一：云存储落地 —— 已全部完成

| 阶段 | 内容 | 状态 |
|---|---|---|
| **CS-1** | 凭据 AES-256-GCM 加密 + `factory` 去写死（驱动注册表 + 向后兼容降级） | 完成 |
| **CS-2** | `CloudStorageConfig` 模型 + 迁移 `0005` + 配置 CRUD（密文入库、读取脱敏） | 完成 |
| **CS-3** | 真实云驱动阿里 OSS / 腾讯 COS / 七牛 Kodo | 完成 |
| **CS-4** | 管理端 `/admin/cloud-storage/*`：配置、activate 热切换、health、presign 直传 | 完成 |
| **CS-5** | 前端「系统设置 → 云存储」页 + 菜单 + 多语言 | 完成 |
| **CS-6** | 历史附件迁移任务（本地 → 云，进度可查、失败可重试） | 完成 |

CS-6 的补充改动（v2.2.6）：迁移结果原本 `done > 0` 就判 `done`，一批 10 条里
9 条失败也显示「已完成」。现改为三档：全成功 `done` / 全失败 `failed` /
有成功也有失败 `partial`，前端 `partial` 用 warning 色。

### 关键设计决策（仍然有效）

1. **接口对齐现有 sync `Storage` 协议**，不照搬 async S3 协议——与全栈 sync 风格一致。
2. **凭据密钥派生自 `JWT_SECRET`**（`SHA256(JWT_SECRET)`）；支持 `JWT_SECRET_OLD` 轮换回退。
3. **向后兼容降级**：未注册/构造失败的云驱动降级为 `local` 并告警，绝不因配置未就绪导致上传中断。
4. **迁移保留本地源文件**：迁移 = 复制上云 + 更新记录。业务表里若存了直连
   `/storage/{key}`，本地文件仍在，旧链接不会断。删除本地作为独立的后续动作。

### 剩余风险

| 风险 | 缓解 |
|---|---|
| `JWT_SECRET` 变更后历史凭据解密失败 | 部署文档明确「上线后禁改 JWT_SECRET」；提供凭据重录 UI |
| 迁移静默失败 | 已由 `partial` 状态暴露，`error` 带末条原因 |
| 历史附件超过 `FILE_MAX_UPLOAD_SIZE` 时迁移失败 | 计入 `failed`；需要时临时调高上限再续跑 |

---

## 2. 方向二：测试与质量加固

| 阶段 | 内容 | 状态 |
|---|---|---|
| **QA-1** | 统一 fixtures + `pytest-cov` 覆盖率门槛 | 完成（v2.2.7）：CI `--cov=app --cov-fail-under=50`，当前 54.75% |
| **QA-2** | 核心闭环集成测试：订单→工单→派工→报工→审核→算薪 | 完成（3 个闭环测试文件） |
| **QA-3** | 安全/RBAC 回归：越权、`require_permissions`、JWT、上传 MIME/XSS | 完成（5 个安全/权限测试文件） |
| **QA-4** | Alembic 规范化 + `upgrade/downgrade` CI 校验 | 完成（15 个版本 + 线性校验） |
| **QA-5** | CI 门禁：pytest + 前端类型检查与构建 | 完成 |

**QA-1 已交付（v2.2.7）**：CI 输出覆盖率并设 50% 门槛；当前 624 项用例、覆盖率 54.75%。
不建议一上来就卡全仓 60%——先把核心域（upgrade / storage / salary / order）
卡住，避免为了达标去写无意义测试。

---

## 3. 方向三：性能与可观测性

| 阶段 | 内容 | 状态 |
|---|---|---|
| **PERF-1** | 结构化请求日志 + SQLAlchemy 慢查询（阈值可配） | 完成；**`/metrics` 未做**（无 prometheus 依赖） |
| **PERF-2** | 热点表索引审计 + 列表强制分页 + N+1 排查 | 完成（268 单列索引 + 关键复合索引） |
| **PERF-3** | Redis 缓存：`public-config`、字典、看板聚合 + 失效策略 | 完成（v2.2.10）：版本化 key + commit 后按 namespace 失效，Redis 故障降级回源 |
| **PERF-4** | 前端路由级分包 + 体积预算 | 完成（`manualChunks`）；element-plus 仍是最大块 |

### 关于剩余的判断

- **`/metrics`**：只有接入监控系统（Prometheus/Grafana）才有意义。单机部署场景下
  `journalctl` + 慢查询日志已经够用，加 `/metrics` 属于「装了没人看」。**建议按需再加。**
- **PERF-3 业务缓存（v2.2.10 已交付）**：失效策略按「版本化 key + Session 级事件」
  实现，矩阵见 `core/business_cache.py` 模块 docstring：public-config / 字典 /
  看板三个 namespace，各自 INCR 版本号失效，Redis 不可用时全量降级回源。
  看板按最终一致设计（60s TTL 兜底）。

---

## 4. 当前建议排期

原排期（第 1~4 周完成全部）已经跑完，实际完成度约 **95%**（QA-1、PERF-3 于 v2.2.7 / v2.2.10 补齐）。剩余部分：

| 优先级 | 事项 | 预估 | 说明 |
|---|---|---|---|
| P3 | PERF-1 `/metrics` | 0.5d | 等有监控系统再补 |
| P3 | 前端 element-plus 按需引入 | 1d | 779kB 可显著压缩，但要防白屏回归 |

---

## 5. 已交付清单（按代码核实）

- **CS-1**：`app/storage/crypto.py`（AES-256-GCM，密钥派生自 `JWT_SECRET`，支持轮换回退、脱敏）；`factory.py` 改为驱动注册表 + 配置解析 + 向后兼容降级；`tests/test_storage_crypto.py`。
- **CS-2**：`models/cloud_storage.py` + `alembic/versions/0005_cloud_storage.py` + `services/cloud_storage_config.py`。
- **CS-3**：`app/storage/drivers/{aliyun,tencent,qiniu}.py` + `base_cloud.py`。
- **CS-4**：`api/admin/system/cloud_storage.py`（config 读写、activate 热切换、health、presign 直传）。
- **CS-5**：`frontend-admin-pro/src/pages/system/CloudStoragePage.vue` + 路由菜单 + 多语言。
- **CS-6**：`services/cloud_storage_migration.py`（本地 → 云，快照 id、sha256 校验、逐条提交、进度实时）+ `api/admin/system/cloud_storage.py` 的 `/migration` 端点 + 前端迁移面板；v2.2.6 增加 `partial` 状态。
- **QA-2~QA-5**：核心闭环测试、安全权限回归、15 个 alembic 迁移与线性校验、CI 门禁。
- **PERF-1**：`core/observability.py`（request_id 中间件 + 慢查询日志，阈值 `DB_SLOW_QUERY_MS`）。
- **PERF-2**：268 个单列索引 + 关键复合索引。
- **PERF-4**：`frontend-admin-pro/vite.config.ts` 的 `manualChunks` 分包。

---

*本版为代码核实后的状态，替代 2026-10-04 的原稿。若后续新增功能，请同步更新本文件
的状态列，避免再次出现「文档说没做、代码早做完」的情况。*
