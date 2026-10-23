# 扩展宿主与扩展开发指南

CenkorMES 支持以「扩展」形式增量交付功能：扩展的安装、授权与分发由独立的
**应用中心**（cenkormes-center）完成；主程序仅保留极薄的「扩展宿主」，负责
加载与门控，不含任何应用商店 / 授权管理界面。

## 一、MES 端配置（backend/.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `EXTENSIONS_ENABLED` | `true` | 是否启用扩展宿主 |
| `EXTENSIONS_DIR` | `./extensions` | 扩展安装目录（相对 `backend/`） |
| `APP_CENTER_URL` | 空 | 应用中心地址；为空 = 本地模式（跳过授权校验，已安装扩展直接启用） |
| `APP_CENTER_INSTANCE_UID` | 空 | 实例 UID（应用中心创建实例时一次性展示） |
| `APP_CENTER_INSTANCE_TOKEN` | 空 | 实例令牌（同上） |
| `APP_CENTER_SYNC_MINUTES` | `30` | 心跳同步间隔（分钟），`<=0` 时关闭后台同步 |

## 二、启用判定（三层叠加）

```
installed（已安装） AND override != disabled（未被本地禁用）
  AND (无中心配置 OR 授权 state == active)
```

- 授权状态来自心跳响应的 entitlements 快照；中心不可达时沿用上次快照（离线容忍）。
- 本地禁用（CLI `disable`）优先级最高，即使授权有效也不加载。
- MES 侧不新建数据库表；全部运行时状态落在 `extensions/.state/*.json`。

## 三、CLI（backend/scripts/extension.py）

```bash
python scripts/extension.py list              # 已装扩展与启用状态
python scripts/extension.py install xxx.zip   # 安装扩展包（自动校验 manifest）
python scripts/extension.py enable <key>      # 本地启用
python scripts/extension.py disable <key>     # 本地禁用（优先于授权）
python scripts/extension.py remove <key>      # 卸载（同时清理本地覆盖）
python scripts/extension.py sync              # 手动触发一次心跳同步
```

## 四、宿主实现（backend/app/extension_host/）

| 文件 | 职责 |
|---|---|
| `manifest.py` | `manifest.json` 读取与校验 |
| `state.py` | 运行时单例与 `.state/*.json` 落盘缓存（授权快照 / 本地覆盖 / 迁移指纹） |
| `loader.py` | `mount_extensions()` 路由挂载 + `require_extension` 授权门控 + `register_events` 接线 |
| `sync.py` | 心跳同步线程（标准库 urllib 实现，无第三方依赖） |
| `host.py` | 启动装配（`mount_all` / `startup_host`）与扩展权限注入（补授 admin） |
| `events.py` | 扩展事件总线（通知型 + 拦截型），详见第十章 |

## 五、MES 侧 HTTP 面

- `GET /api/admin/extensions` — 已装扩展与启用状态（admin 前端加载器消费）
- `GET /api/admin/extensions/{key}/plugin.js` — 前端插件脚本（仅启用状态可获取）
- `/api/extensions/{key}/...` — 扩展后端路由（登录鉴权 + 授权门控由宿主自动附加）

## 六、前端扩展加载器（admin 端）

- 应用启动时注入 `window.Vue` 并安装 `window.__registerExtension` 注册桥。
- 登录后首次路由通过时拉取 `/api/admin/extensions`，对 `enabled && has_frontend`
  的扩展注入 `plugin.js`（Blob 动态执行）。
- 插件注册的动态路由挂载到 `app-layout` 之下，菜单渲染为侧边栏「扩展应用」分组，
  多语言经 `i18n.mergeLocaleMessage` 注入；菜单 `permission` 同时约束路由访问。
- 源码位置：`frontend-admin-pro/src/utils/extensionLoader.ts`。

## 七、本地开发流程（不接应用中心）

1. `cp -r backend/extensions_samples/quotation_demo backend/extensions/my_ext`
2. 修改 `manifest.json`（`key` 与目录名一致）与 `router.py` / `plugin.js`
3. 重启后端（本地模式会自动加载）；`python scripts/extension.py list` 可查看状态
4. admin 前端登录 → 侧边栏出现「扩展应用」分组与菜单

## 八、对接应用中心（生产）

1. 应用中心「实例管理」创建实例 → 将一次性展示的 uid / token 写入 `.env`
2. 上传扩展包（zip）→ 发卡（绑定该实例，可设有效期）
3. 重启后端 → 心跳线程启动，授权自动同步（吊销 / 过期也在下一轮心跳生效）
4. 版本更新：应用中心上传新版本并发布 → 客户侧 `extension.py install` 新包完成 OTA

> 扩展包制作规范（manifest / router / migrations / plugin.js）见应用中心仓库
> `docs/extension-spec.md`；可运行样例见 `backend/extensions_samples/quotation_demo/`。

### 八·补：本节的现状校正（2026-10-09 只读核对）

上面 1–4 是设计初稿，与现在代码有几处出入，按代码为准：

- **不走 `.env`**。hub 地址存 `platform_settings.market_hub_url`（市场页设置，`PUT /admin/market/hub`），
  实例凭证经**设备码绑定**换发的 `market_instance_token`（`POST /admin/market/bind/start` → 门户
  `/connect` 确认 → `GET /admin/market/bind/poll`），同样落 `platform_settings`。没有 uid/token 的 `.env` 项。
- **发布有审核闸门**：开发者在 cenkor-admin「开发者应用中心」提交 zip → `app_submissions.status=pending`
  → 人工审核 `POST /submissions/{id}/review`（approve/reject）→ 只有 `approved/installed` 才能被目录列出、
  被 `cloud/packages/{app_key}` 分发。`approve` 即上架，没有独立的 publish 步骤。
- **OTA 入口在市场页**，不是 CLI：`POST /admin/market/install`（需已持有该 app 的有效 license_key），
  装完 `hot_setup_extension` 即时生效，**不需要重启后端**（前提：单进程 uvicorn）。
  `backend/scripts/extension.py` 现在主要用于本地启停覆盖（`overrides.json`）。
- 心跳周期：web 进程内 daemon 线程每 **15 分钟**刷一次已购快照（`ENTITLEMENT_SYNC_MINUTES`），
  打开市场页也会顺手刷一次；hub 不可达时**保留上次快照**（fail-open，不误停用正在运行的扩展）。

已知缺口（哈希不校验、hub_url 可写、审核权限复用 `rbac:role:write`、`latest_version` 缺失等）
统一记在 `AUDIT_REPORT_2026-10.md` §9，待修复。


## 九、本批上架的三个 AI 扩展（2026-10-17）

面向实例运维。这三个包由应用中心（cenkor-admin）分发，**不进 cenkormes 核心仓**，
安装后落在 `backend/extensions/<key>/`，各含 5 件套：`manifest.json` / `router.py` /
`migrations.sql` / `frontend/plugin.js` / `README.md`。当前线上版本 **1.0.2**。

| key | 菜单（admin 左侧） | 路由前缀 | 自有表 |
|-----|-------------------|----------|--------|
| `ai_scene_reports` | AI 场景文书 → `/ext/ai-scene-reports` | `/api/extensions/ai_scene_reports` | `ext_ai_scene_reports_docs`、`…_config` |
| `ai_insight` | AI 深度洞察 → `/ext/ai-insight` | `/api/extensions/ai_insight` | `ext_ai_insight_runs`、`…_config` |
| `ai_knowledge` | AI 知识库 → `/ext/ai-knowledge` | `/api/extensions/ai_knowledge` | `ext_ai_knowledge_docs`、`…_chunks`、`…_logs`、`…_config` |

权限码统一 `ext.<key>.view`（看与用）/ `ext.<key>.manage`（改参数），装包时宿主自动补授 admin。
三个包共用一套边界：**取数一律只读**，写操作只碰自己的 `ext_ai_*` 表；`ai_knowledge`
的向量索引落在 `backend/data/ext_ai_knowledge/`（独立目录，不与宿主 `data/chroma_db` 混用）。

功能面（细节看包内 README，这里是口径）：

- **AI 场景文书**：三类一键生成并归档 —— 交接班记录 `shift_handover`、待审报工摘要
  `pending_audit`、订单交期风险分析 `plan_risk`。
- **AI 深度洞察**：五路 —— 质量缺陷模式 `quality_defect`、SPC 过程判异 `spc_abnormal`、
  设备健康与可靠性 `equipment_health`、交期与产能负荷 `delivery_capacity`、
  成本异常波动 `cost_anomaly`；每次洞察落 `…_runs`（含耗时与 token 成本）。
- **AI 知识库**：向量优先、关键词兜底的双通道检索 + 严格基于命中片段的问答，可按业务域
  与权限码限定可见范围。

### 九·1 前置条件

1. 实例已完成设备码绑定，且**持有该 app 的有效 license**（市场页显示「已持有授权」）；
   否则 `install` 会被拒。
2. 「AI 网关/模型」总开关与模型配置。**未配置不会报错**：文书与洞察走规则层，
   知识库降级为关键词检索，接口仍 200，并在响应里给 `ai_unavailable` / `note` 说明原因。
   注意 `/status` 里的 `vector_ready` 只代表**本地向量库能打开**，不代表 embedding 服务可用。

3. **向量通道要两处配齐**（2026-10-17 端到端实测通过的口径）：
   - **平台侧**「系统设置 → AI 网关/模型」：新建网关（Base URL + API Key + 启用）→ 该网关下加一个
     **对话**模型并设为默认 → 打开页面顶部总开关。
     ⚠️ 不要把向量模型设成默认对话模型（1.0.3 起也可以不改默认，见下面第 4 条）—— 实测拿 `doubao-embedding-vision` 去 chat 返回
     `HTTP 500 InternalServiceError`，AI 文书与洞察的增强会整体退回规则层
     （扩展会如实置 `ai_unavailable=1` 并在 `ai_hint` 给出原因，不报错、不空页）。
   - **应用侧**「AI 知识库 → 参数设置 → embedding 模型」：**必须显式填**该供应商真实开通的向量模型名。
     取值链是 `扩展参数 → settings.RAG_EMBEDDING_MODEL → 兜底 "text-embedding-3-small"`，
     留空就等于用 OpenAI 的模型名，非 OpenAI 网关必然失败降级。
   - 火山方舟实测口径：Base URL 用账号自己的接入点（本例 `https://ark.cn-beijing.volces.com/api/plan/v3`）；
     `doubao-embedding-vision` 走**标准 `/embeddings` 即可用**，输出 2048 维（别名解析到 `-251215`）；
     纯文本向量模型若未开通会返回 `404 UnsupportedModel`。
   - 换 embedding 模型时注意向量维度：本地 Chroma 集合以**首次写入的维度**定型，
     中途换不同维度的模型会导致写入冲突（只报「写入向量库失败」）。换模型请先改「collection 名」
     再执行一次「批量重建索引」。

4. **1.0.3 起：chat 与向量可以各打各的网关**（2026-10-17 发布，解决「一个默认模型被两边抢」）：
   - 三个应用的「参数设置」多了一个**对话模型标识**输入框，AI 知识库还多一个**向量模型标识**。
     填的是「系统设置 → AI 网关/模型」里**模型行的标识（code，如 `A001` / `MiniMax-M3`）**，不是 Model ID。
   - 留空 = 跟随平台默认模型。所以两种配法都成立，任选其一：
     - **A（推荐，改动最小）**：把默认模型设成**对话**模型 → AI 文书 / 洞察零配置即可用；
       只在 AI 知识库填「向量模型标识」指向向量模型那一行。
     - **B**：默认模型保持向量模型（embedding 零配置）→ 三个应用都填「对话模型标识」。
   - ⚠️ 填错**不报错**：宿主 `resolve_runtime` 按标识找不到模型行时会静默回落到默认模型，
     所以填完务必看应用回显的「当前生效模型」确认，别只看保存成功。
   - 维度记账：1.0.3 把维度与模型名记进 `ext_ai_knowledge_config`（`embed_dim` / `embed_model_used`）
     并写进集合 metadata。已有向量与新向量维度或模型不一致时**拒写并给出可读原因**
     （以前只会报一句「写入向量库失败」）。处理办法：「批量重建索引」勾选「重建集合」，
     集合会删掉重建 —— 历史向量不可恢复，等于全量重新向量化一次，按文档量评估调用费用。
   - 体检页 `llm_ready` 改为真实判定（此前硬编码 True）：生效模型疑似向量模型（名字含 `embedding`）
     时置 false，并在 `llm_note` 里说明去哪改。

5. **1.0.4 起：AI 知识库问答记清「是谁答的」**（2026-10-17 发布，只动 ai_knowledge 一个包）：
   - `/ask` 返回体与留痕表 `ext_ai_knowledge_logs` 增记 `ai_model` / `tokens_in` / `tokens_out`。
     此前只有 AI 文书 / 洞察记模型，知识库答完不知道是哪个模型答的，成本归因断一层。
   - 只在模型**真答出来**时才记 `ai_model`；调用失败 / 没配网关一律留空，免得留痕像是它答的。
   - `answered` 改按「大模型是否真答出来」记录：原先关掉 AI（`use_llm=false`）也记成已作答。
   - 降级文案分流：用户自己关掉 AI 显示「未开启 AI 解读」，网关解析或调用失败才显示「AI 解读不可用」。
   - ⚠️ 存量库补列靠**一次性幂等脚本** `_migrate_knowledge_logs_ai_model.py`，不能写进 `migrations.sql`：
     MySQL 8.0 不认 `ADD COLUMN IF NOT EXISTS`（那是 MariaDB 语法，实测 1064），裸 `ALTER ADD` 重跑又报
     Duplicate column，安装期重跑会把启用流程整个回滚。缺列期间 `/ask` 与 `/logs` 自动回退 1.0.3 字段集，
     不报错、补完也不用重启服务。

### 九·2 安装 / 更新 / 卸载（2026-10-17 实测）

> **已被「十一、全生命周期（插拔闭环 v2）」取代（2026-10-22）。** 下面记录的是 v1
> 半开环实现（安装前 `rmtree` 旧目录、卸载只删目录 + 卸路由），仅作历史留档；
> 现行安装/更新/卸载/回滚/修复语义见 `docs/EXTENSION_LIFECYCLE.md`。

入口都在 admin「应用市场」页，对应 `POST /admin/market/install`、`POST /admin/market/uninstall`。
**单进程 uvicorn 下全程热生效，不需要重启后端**；只有整进程重启才归运维手动执行。

卸载回归拿 `ai_knowledge` 跑了「卸载前 → 卸载后 → 重装后」三轮快照比对（22 项指纹）：

- 卸载只做 `shutil.rmtree(extensions/<key>/)` + 热卸载路由。实测**不 DROP 任何 `ext_ai_*`
  表、不清 `.state/migrations.json`、不动 `.state/entitlements.json` 与 license、
  不删 `data/ext_ai_knowledge/` 向量目录**，权限点也保留。
- 卸载后：`GET /api/admin/extensions` 清单里该 key 消失（菜单随之消失），
  `GET /api/extensions/ai_knowledge/status` → 404，相邻扩展接口不受影响。
- 重装后：`router.py` 与卸载前**字节级相同**；4 张表、行数、`top_k` / `enabled` 等参数
  原样回来。唯一变化是 `.state/migrations.json` 指纹从 `1792197145:4460` 变
  `1792201110:4460` —— `mtime:size` 里的 mtime 变了（重新落盘），size 不变，
  说明迁移按幂等 DDL 重跑了一遍，没有重复建表也没有清数据。
  **结论：卸载/重装不会丢业务数据，但也不会替你清库**；要真清数据得手工 DROP。

### 九·3 边界（本批明确不做）

- **文档格式**：知识库只接受在线粘贴与 `.txt` / `.md` 上传。**不支持 docx / pdf**
  （实例未装 `python-docx` / `pymupdf`，本批不新增依赖），也不支持图片 OCR、URL 抓取、批量导入。
- 单篇正文 20 ~ 200000 字符，超出直接拒。
- 不做实时预警（那是 `ai_anomaly`）、不做异常排查（那是 `production_diagnosis`），
  洞察是「按路聚合 + 留痕对比」的定位。
- 不自带 embedding 模型服务；向量通道复用平台 AI 网关的 OpenAI 兼容 `/embeddings`。

### 九·4 同类扩展开发必读的三处坑（都已进闸门 `mes-extensions/_selftest/manifest_check.py`）

1. **`INSERT` 后要在 `db.commit()` 之前取 `LAST_INSERT_ID()`**。先 commit 会把连接归还连接池，
   随后的 `SELECT` 可能落到另一条连接上，返回的是它的旧自增值 —— 1.0.1 实测返回 `2`
   而真实行号是 `7`，前端拿这个 id 回读详情必然落空，知识库侧还连带分块与向量化 0 产出。
2. **`plugin.js` 的 `setup` 必须返回渲染函数**：`setup: function () { … return function () { return h(…) } }`。
   写成 `return { render: function () {} }` 时 Vue 3 把它当 bindings，组件既无 template 也无 render
   → **整页空白且不报任何错**。老包 24/24 都是前一种写法。
3. **实例的信封是「HTTP 恒 200，业务码在 `body.code`」**。判 401/404 要看 body，
   不能只看 HTTP 状态码；`plugin.js` 的真实入口是 `GET /api/admin/extensions/{key}/plugin.js`
   （带 `/api` 前缀且需登录），不带 `/api` 会被 SPA 兜底页吃掉、返回一个 1035 字节的 index.html。

### 九·5 批量安装商业应用后的全量只读冒烟（2026-10-17 实测）

给门户买家（`portal_user_id=21` / `product=cenkormes`）补发 23 张授权并 `POST /install` 一次性装上后，
对全部 27 个扩展的 120 个无参 GET 端点做只读冒烟，逐一命中并归类 `body.code`。结论与踩坑：

- **成片 403「无权限」**：安装瞬间 `hot_setup_extension` 里 `_sync_permissions()` 与
  `run_extension_migrations()` 都有 `if not is_enabled(key): continue`；而那一刻内存授权快照还是
  发卡前的旧内容（`is_enabled=False`），于是这批扩展的 `ext.*.view/manage` 权限点没写库、也没补授 admin。
  权限校验 `get_user_permission_codes` 每请求实时读库，**补写权限点 + 补授 admin 即刻生效、无需重启**。
- **成片 500「表不存在」**：同一道 `is_enabled` 门控把 `migrations.sql` 整段跳过（`.state/migrations.json`
  当时仍只有 5 条），各 `ext_*` 表压根没建。对「有 migrations.sql 且指纹未记录」的扩展补跑一遍
  （均 `CREATE TABLE IF NOT EXISTS`，幂等）并回写 `mtime:size` 指纹即恢复。
- **行业套件 500（apparel/auto_parts/electronics）**：真实代码缺陷，已修复发版——
  ① 三套件的取数 helper 写成 `db.execute(text(sql), p)`，而 dashboard/summary 类调用方又先包了
  `text(...)`，双重包裹触发 `expected string or bytes-like object, got 'TextClause'`（list 类传裸串不受影响）；
  加 `_sql()` 归一器（str 才包、TextClause 原样）一次兼容。② electronics `/stations` 用 `wo.code`，
  但核心 `work_orders` 无 `code` 列，工单编号在 `orders.code`，改多 JOIN 一层 `orders`。
  发布链：`pack --build` → `publish --apply` → 实例 `POST /install`（会 `rmtree` 重解压、经
  `_load_module` 重新 `exec_module` 加载新代码，**热更新无需重启**）。apparel/auto_parts→1.0.1（hub id 104/105），
  electronics→1.0.2（hub id 107，含 `/stations` 修复）。
- **最终：120 端点 119 直接 200**；唯一非 200 是 `ai_scene_reports /preview` 缺必填 `type` 参数时的
  正常校验 400，带 `?type=shift_handover` 即 200。

> 一句话：批量安装「成功返回」≠「立即可用」——凡安装期依赖 `is_enabled` 内存快照的副作用（建表、注权限、
> 挂路由），都要在授权快照刷新后统一补偿一次。

### 九·6 ai_assistant 从「说明书机器人」升级为 Agent（2026-10-17）

**背景判定**：原 `ai_assistant`（1.0.1，322 行）只是带内置语料的单发聊天机器人——`chat()` 走核心 `chat_completion` 单轮、8 个 `_CONTEXT_PROBES` 固定聚合 COUNT（每条消息现查、但无维度/条件）、`CORPUS` 15 条关键词倒排。核心 AI 客户端 `app.services.ai.client.chat_completion` **不支持 `tools=`**，且 8 个 AI 扩展互不调用（孤岛）。

**升级做法（不改 cenkormes 核心）**：全部落在 `mes-extensions/ai_assistant/router.py`（宿主按单文件加载，故 registry/tools/engine 内联为分节，与 ai_anomaly 等一致）。
- 扩展用 `resolve_runtime()` 返回的 `base_url/api_key/model` **自建 OpenAI 客户端**透传 `tools=`，做多轮 function calling（`MAX_ROUNDS=4`，末轮不注入 tools 逼终答）。
- 轻量 `@_tool` 注册表 + 工具级 RBAC（复用核心只读 `get_user_permission_codes`）：15 个只读工具 = M1 直连核心表 7 个（`overview_stats/query_orders/work_order_progress/report_throughput/equipment_status/quality_defects/inventory_levels`，SQL 对照 information_schema 真实列）+ `search_manual` + M2 环回 7 个（`biz_overview/analyze_anomalies/biz_insight/energy_overview/spc_overview/ask_knowledge/gen_scene_doc`）。
- M2 跨扩展经**环回 HTTP 自调用**（`httpx`→`/api/extensions/<key>/…`，**转发调用者 Authorization**，由目标扩展 `require_extension`+权限门天然鉴权；解析 `body.code`）。`ask_knowledge`→`ai_knowledge/POST /ask`（真向量 RAG），把 8 孤岛接成对话可调能力。
- 新端点 `POST /agent`（多轮+`tool_trace`+优雅降级回 chatbot）、`GET /tools`（列当前用户可用工具）；保留 `/chat`。前端 plugin.js 加「业务助手(Agent)/普通对话」模式开关 + tool_trace 折叠展示。

**版本链**：`1.1.0`（Agent 首版，hub id 108）→`1.1.1`（健壮性：`_agent_turn` 把网关/限流异常统一转 `AiCallError` 触发优雅降级而非 500；剥离 MiniMax-M3 的 `<think>…</think>`，hub id 109，sha `13c0ebc1…` 三方一致）。实例 `POST /market/install` 热更 `hot_loaded=True`，零重启。

**实测**：`query_orders`→engine=agent 基于真实数据作答（近7天0单/逾期3，模型如实标注口径不杜撰）；`biz_overview`+`analyze_anomalies`（M2）→给出健康分偏低、27 项风险(18 critical)、设备保养逾期52天等真实诊断。`/chat` 回归正常，`plugin.js` 200，离线自测 `_selftest/_ai_assistant_agent_selftest.py` 16/16 全绿。测试会话（kind=agent + 指定 chat id）按 id 精确清理，未动生产数据。

> 一句话：cenkormes 侧「Agent 化」的关键不在多写工具，而在①扩展层绕开核心客户端自建 tools 通道；②用环回 HTTP + 转发令牌把各分析扩展接成可调用工具。写操作与工具级二次确认（M3）留后续。

### 九·7 ai_assistant M3：写操作 + 服务端一次性令牌二次确认（2026-10-18）

把 Agent 从「只读查询」推进到「可写业务」，但严守护栏：**任何写都必须经服务端固化的
一次性令牌二次确认后才落库**，且默认只产出可逆草稿。仍不改 cenkormes 核心，写动作复用
核心 crud（`app.crud.order.create_order/confirm_order`、`app.crud.customer.create_customer`、
`app.services.code_generator.resolve_code/BizType`），只调用不修改。

- **三个写工具**（`is_readonly=False`，各自带 `confirm_message`，工具级 RBAC）：
  - `create_draft_order`（`order.create/manage`）：按名/编号解析客户与在用 SKU，生成单号后建**草稿**（status=draft，不提交审批，可 `DELETE /orders/{id}` 撤销）。
  - `confirm_order`（`order.edit/manage`）：草稿/待确认 → 已确认（**不可由助手撤销**，仅经显式确认执行）。
  - `create_customer`（`customer.manage`）：重名预检后建客户档案。
- **引擎写拦截**：`run_agent` 命中写工具时**绝不执行 handler**，改为返回 `pending_action`
  （`tool_trace` 标 `await_confirmation`）。写工具仅在 AI 网关可用时才进 schema（离线/降级不暴露，避免闲聊误提议写）。
- **服务端二次确认（强于 lightmes 现实现）**：新增表 `ext_ai_pending_actions`（token UNIQUE、
  user_id、tool_name、args_json、expires_at +15min、consumed_at、result_json）。`POST /agent`
  把提议参数**固化入库**并下发一次性 `token`；`POST /act {token}` **只认令牌**，name/args 一律从库里读
  （客户端无法篡改参数），消费前复核工具级权限，成功才 `commit` 并置 `consumed_at`，失败 `rollback`
  且保留待确认可重试至过期。前端 plugin.js 渲染「确认执行/取消」卡片，`/act` 走完整信封 `body.code` 判定。
- **可逆性分级**：建草稿=可删；确认订单=不可逆；建客户=删除不干净。故 E2E 仅对「建草稿」跑全生命周期并删除，
  确认/建客户只验提议 + 令牌 + 权限/回滚路径，不真正落不可逆写。

**版本链**：`1.2.0`（M3 首版，hub id 110，sha `e579bd96…`）→`1.2.1`（修 `/act` 在 conv 为空时未提交
`consumed_at` 致令牌可重放，hub id 111，sha `b1219ed9…`）→`1.2.2`（修 `_ensure_conversation` 在
`commit()` 后取 `LAST_INSERT_ID()` 的连接池串号缺陷——新建会话插入消息触发 `ext_ai_messages` 外键 500，
同时波及 `/chat`；改为 commit 前取 id，hub id 112，sha `a773eec6…`，三方 sha256 均一致）。实例热更
`hot_loaded=True`，零重启。

**实测**：离线自测 22/22（写工具恰 3 个且带确认文案、网关离线 schema 不含写、引擎写拦截 handler 零调用、
`execute_write` 只读护栏、`_explain_write` 文案）；实例端到端 14/14：建草稿→`/act` 落库可查→重放令牌 409→
删草稿可逆；未知/非本人/过期/只读令牌分别 404/403/410/400；建客户重名执行期 400 且已回滚（未新增）；
真实 MiniMax `/agent` 明确指令→`pending_action` 且落一条未消费待确认。测试会话/待确认行/自建草稿按 id
精确清理，`user1 会话=0 待确认=0 消息=0`，无残留订单与客户，未动生产数据。

> 一句话：M3 的关键不是「让 Agent 能写」，而是「写被拆成提议(模型产出)+服务端固化(防篡改)+一次性令牌消费(执行)」
> 三段，且默认只落可逆草稿——这比 lightmes 现有 `/act` 直接执行客户端传入 name/args 更稳。

### 九·8 ai_assistant M4：草稿单闭环写工具（1.3.1 上线，2026-10-18）

新增两个写工具（同样走服务端一次性令牌二次确认，均属可逆操作）：
- `update_draft_order`（order.edit/manage）：仅草稿可改——到期日/备注/整单替换明细，核心 `update_order_items` 自动重算金额。
- `cancel_draft_order`（order.edit/manage）：仅草稿且无工单/生产计划关联时可删（核心 `delete_order` 自带状态守卫），建错就地撤销。
前端确认卡片增「改参数重新提议」按钮：args 回填输入框，用户改后重发走新一轮服务端固化（不改防篡改模型）。工具总数 18→20（写 5）。`1.3.0` hub id 113；`1.3.1` hub id 114（sha `377a3e24…`，三方一致），实例热更 `hot_loaded=True`。

> 版本插曲（如实记录）：`1.3.0` 含缺陷——`update_draft_order` 返回体误取不存在的 ORM 属性 `total_amount`（真实属性 `amount`），执行改草稿在 flush 后 AttributeError，被端点兑底捕获返 400+可读错误（实测：零脏数据、失败令牌未消费可重试）。修复版 `1.3.1` 发布后终验 **12/12 全绿**：建→改（备注/交期/明细 qty=7 替换+金额重算）→删全生命周期可逆；qty=0 拒绝且订单原样；LLM 真实提议 update_draft_order 走二次确认；测试数据零残留。

## 十、事件钩子（2026-10-19）

商业扩展不能只做「独立功能页」，必须能**挂到核心业务上**：当报工、审核、派工、发薪等核心动作发生时，扩展能被回调参与业务。事件钩子就是这条接线。

宿主提供一个**纯内存事件总线**（`backend/app/extension_host/events.py`，单例 `event_bus`），核心业务在关键点位发事件，扩展订阅后被回调。**不新建任何数据库表、无迁移**；与飞书 `notify_dispatcher` 的 `event_code` 体系是**两个独立注册表**（命名词汇对齐，但互不串台，飞书行为零改动）。

### 十·1 两种钩子（语义对照）

| | 通知型 notify | 拦截型 intercept |
|---|---|---|
| 触发时机 | 事务 **commit 成功之后** | 事务 **commit 之前** |
| 执行方式 | 异步（总线自有线程池，4 worker） | 同步（请求线程内，经线程池以获得超时能力） |
| 能否影响核心业务 | **不能**——只读+副作用，handler 异常被逐个隔离 | **能**——返回 `allow=False` 即否决本次操作 |
| 回滚时 | 不发（commit 没成功就没有事件） | ——（否决则根本不会 commit） |
| 故障策略 | 异常吞掉记日志，绝不上抛 | **fail-open**：异常/超时/扩展禁用一律放行+记日志 |
| 典型用途 | 写扩展自有统计表、推外部系统、留痕 | 合规校验、阈值拦截、权限/资质门禁 |
| 订阅 API | `bus.subscribe(key, name, handler)` | `bus.subscribe_intercept(key, name, handler, *, timeout=None)` |
| handler 签名 | `handler(event) -> None` | `handler(event) -> InterceptDecision \| None` |

> 首期拦截型**只开放报工提交两个点位**（`report.submitting` / `report_unit.submitting`）。拦截是否决权，点位越多风险面越大，后续按需逐个评审再放。通知型已全量铺开闭环 18 个点位。

### 十·2 扩展怎么接（register_events 约定）

在扩展的 `router.py` 里**可选**导出一个模块级函数 `register_events(bus)`。宿主加载扩展模块后自动调用它完成订阅（不新增 `plugin.py`，`manifest.json` 不加字段）：

```python
from app.extension_host.events import EventBus, InterceptDecision

def register_events(bus: EventBus) -> None:
    def on_report_submitted(event):
        # 通知型：commit 后于后台线程执行。取数一律用 bus.open_session()
        p = event.payload
        with bus.open_session() as db:
            db.execute(text("INSERT INTO ext_xxx (...) VALUES (...)"), {...})
            db.commit()

    def guard_report(event):
        # 拦截型：commit 前同步执行，返回 allow=False 即否决
        if int(event.payload.get("bad_qty") or 0) > 0 and not str(event.payload.get("remark") or "").strip():
            return InterceptDecision(allow=False, reason="有不良品必须填备注")
        return None  # 放行

    bus.subscribe("my_ext_key", "report.submitted", on_report_submitted)
    bus.subscribe_intercept("my_ext_key", "report.submitting", guard_report)
```

接线细节（宿主侧，扩展无需关心）：
- `loader.py` 加载 `router.py` 后调 `_register_events`：**先按 key 反注册再订阅**（热重载幂等，不产生双份 handler）；`register_events` 抛异常**仅记 error 日志，不影响路由挂载**——钩子是增强，不是加载前提。
- `host.py::hot_teardown_extension`（卸载/热更）会 `unsubscribe_extension(key)` 摘除该扩展全部订阅。
- 没有 `register_events` 的老扩展自动跳过，**零破坏**。

> ⚠️ **`register_events` 在「模块导入期」被调用——只创建闭包+登记订阅，禁止任何 DB / 网络 / 文件 IO。** 真正的 IO 发生在事件触发时的 handler 内。导入期做 IO 会拖慢甚至炸掉扩展加载。

### 十·3 事件契约表（EVENT_CATALOG，稳定契约·只增不改）

源码：`events.py::EVENT_CATALOG`。订阅未收录的事件名只 warning 不拒绝（允许扩展先行、核心后补），但下表事件是宿主已埋点、保证会发的。

**拦截型（commit 前，可否决）**

| 事件名 | 触发点位 | payload 字段 |
|---|---|---|
| `report.submitting` | H5 批量报工提交（`api/h5/tasks.py`） | `report_id, task_id, task_code, report_user_id, good_qty, bad_qty, remark` |
| `report_unit.submitting` | H5 单件报工提交（`api/h5/report_units.py`） | `report_unit_id, task_id, task_code, unit_seq, piece_id, result_type, user_id` |

**通知型（commit 后，只读+副作用）**

| 事件名 | 触发点位 | payload 字段 |
|---|---|---|
| `order.created` | 订单创建 | `order_id, code, customer_id, item_count, total_qty, amount(str)` |
| `order.confirmed` | 订单审核通过 | `order_id, code, customer_id` |
| `order.rejected` | 订单驳回 | `order_id, code, reason` |
| `plan.created` | 生产计划创建 | `plan_id, order_id, code` |
| `plan.auto_scheduled` | 计划自动排产（排日期） | `plan_id, mode, start_date, end_date` |
| `plan.released` | 计划确认下发（含自动派工触发的自动下发） | `plan_id` |
| `plan.auto_dispatched` | 计划自动派工完成 | `plan_id, dispatched_count, task_count` |
| `task.assignments_set` | 任务派工（设定人员分工） | `task_id, task_code, assignments[{user_id, assigned_qty}]` |
| `report.submitted` | H5 批量报工提交成功 | `report_id, task_id, task_code, report_user_id, good_qty, bad_qty, remark` |
| `report_unit.submitted` | H5 单件报工提交成功 | `report_unit_id, task_id, task_code, unit_seq, piece_id, result_type, user_id, anomaly_confirmed` |
| `report.leader_approved` | 报工班组长审核通过 | `report_id, task_id, approver_id` |
| `report.qc_approved` | 报工质检终审通过（生成计件工资） | `report_id, task_id, approver_id, salary_item_ids[]` |
| `report.rejected` | 报工驳回 | `report_id, task_id, approver_id, reason` |
| `report_unit.approved` | 单件报工终审通过 | `report_unit_id, task_id, approver_id, salary_item_id, piece_id, stage` |
| `report_unit.rejected` | 单件报工驳回（含质检致命缺陷自动驳回） | `report_unit_id, task_id, approver_id, reason` |
| `salary.time_items_generated` | 计时工资项生成 | `date_from, date_to, item_count, total_amount(str)` |
| `salary.slip_paid` | 工资条发放（单条/批量） | `month, slip_ids[], user_ids[], total_amount(str)` |
| `salary.slip_signed` | 工资条签名确认 / 拒签 | `slip_id, user_id, action(sign/reject), month` |

> 契约稳定性：上表**只增不改**——已有事件名与字段含义不变，新点位以新事件名追加。扩展可放心硬编码订阅。

### 十·4 payload 铁律 + 取数范式

- **payload 只允许 JSON 原语**（`int/float/str/bool/None/list/dict`）。`Decimal→str`、`datetime/date→ISO 字符串`、`UUID→str` 由总线自动转；**禁止塞 ORM 对象**——物化时遇非法类型直接抛错、事件丢弃（记日志，不影响业务）。
- 为什么禁 ORM：通知 handler 在 **commit 后于另一线程**执行，此时请求 session 已失效/对象已 expire，摸 ORM 属性必炸。
- **要详情就按 payload 里的 ID 回查**，回查用 `bus.open_session()`（handler 专用独立 session，用完自动 close），**绝不共享请求 session**：

```python
def handler(event):
    with bus.open_session() as db:
        task = db.get(Task, event.payload["task_id"])   # 按 ID 回查
        ...
```

- 拦截 handler 同理**看不到本次请求未提交的数据**（它在 commit 前、且在独立线程执行）——判断依据只能是 **payload + 已提交状态**。所以核心埋点会把否决所需的关键字段（数量、ID、备注等）全塞进 payload。

### 十·5 拦截型：fail-open / 只读 / 超时预算

- **fail-open（定稿）**：handler 抛异常、超时、或扩展被禁用 → **一律放行**并记 error 日志。扩展故障绝不能阻断生产。
- **超时预算**：默认 `settings.EXTENSION_HOOK_TIMEOUT = 5.0` 秒（`backend/app/core/config.py`），可在 `subscribe_intercept(..., timeout=)` 单点覆盖。超时的 handler 线程杀不掉，任其后台跑完——所以**拦截 handler 必须只读**，最坏情况是白跑一趟，不留副作用。
- **多扩展不短路**：同一事件的所有拦截 handler 全部执行完，任一 `allow=False` → 整体否决；否决原因按订阅序合并。
- **否决的响应形状**：沿用全系统既有约定——**HTTP 200 + `body.code = 400`**（`main.py` 全局 handler 把 `HTTPException` 转成此形状），`detail` 为 `扩展拦截：[ext_key] 原因；…`。**前端零改动**即可展示。否决 → 无 commit → flush 的数据随连接回收，**无脏数据**。

### 十·6 门控与反注册（运行期即时生效）

- **分发时**逐个查 `runtime.is_enabled(key)`（订阅时不查）：运行期 `disable` / 授权吊销**即时生效**，连正在飞的事件也会跳过该扩展。
- 卸载 / 热更 / `runtime.reset()` 都会清掉对应订阅，不留悬挂 handler。
- 进程关闭时 `main.py` 的 shutdown 钩子调 `event_bus.shutdown(wait=False)` 关线程池。

### 十·7 样例与测试

- **样例包**：`backend/extensions_samples/hook_demo/`——`register_events` 订阅 `report.submitted`（写自有表 `ext_hook_demo_report_log`）+ `report.submitting`（演示「有不良品必须填备注」否决）。照抄即可起步。
- **测试**：`backend/tests/test_extension_events.py`（总线语义 15 例）+ `test_extension_event_hooks.py`（端点级拦截/通知/样例 6 例）。均走 SQLite 夹具，不碰生产库。
- **生效**：改完由运维**自行重启 cenkormes API**；扩展侧无需任何动作。

## 十一、全生命周期（插拔闭环 v2，2026-10-22）

> **本节取代「九·2 安装 / 更新 / 卸载」的旧描述。** 九·2 记录的是 v1 半开环实现（安装前
> `rmtree` 旧目录、卸载只删目录 + 卸路由），仅作历史留档。现行行为以
> `docs/EXTENSION_LIFECYCLE.md` 与 `backend/app/extension_host/lifecycle.py` 为准。

### 十一·1 一次操作的五步

| 步骤 | 做什么 | 失败时 |
|---|---|---|
| preflight | key 正则、manifest v2、product、semver、`min_core_version`、依赖、包 SHA256、zip 成员白名单、路由/菜单/权限/表名冲突 | 400/409，`extensions/` 目录零改动 |
| stage | 解压到 `extensions/.staging/<key>-<version>-<uuid>/` | 删 stage，live 不动 |
| backup | 旧目录复制到 `extensions/.backup/<key>/<version>-<ts>/`（保留最近 3 份） | 中止，live 不动 |
| migrate + swap | 只跑该扩展的新迁移；`os.replace` 换入，第二步失败立即换回 | 自动回滚上一版并重新挂载 |
| activate + health | 同步权限 → 挂路由 → 注册事件/任务 → 健康检查 → 写 registry/审计 | 回滚 + 写 `last_error` |

不变量：live 目录永远是完整可运行版本；`.staging` 不扫描、不挂载、不进 registry；迁移成功前不换入。

### 十一·2 卸载与彻底清除（默认保留数据）

1. `runtime.retiring.add(key)`，`require_extension` 对新请求返回 503，等 2 秒排空。
2. 从 `app.router.routes` 移除路由；`event_bus.unsubscribe_extension(key)`。
3. 按 manifest `tasks.celery` 从 Celery 注册表移除，删 `beat_schedule` 里该 key 的条目；失败只记 `worker_restart_required`。
4. 删 `role_permissions` 中 `ext.<key>.*` 的绑定，再删 `permissions` 同名权限点（不碰其他前缀）。
5. 清 `sys.modules` 子树、`app.state` 缓存、`runtime.overrides[key]`。
6. 目录移入 `extensions/.trash/<key>-<ts>/`；registry 标记 `uninstalled_keep`。
7. `purge=true` + `confirm_key=<key>` 才彻底清除：先 JSONL 导出到 `data/.purge_backups/<key>-<ts>/`，再按依赖逆序 DROP **own 表**（manifest `mode=own` ∪ `migrations.sql` 的 `CREATE TABLE`，减核心表与其他扩展表 denylist），最后删 `data/<key>/` 与 state 记录；导出失败默认终止。

重装：`keep` 状态下同 key 再装，表/文件/权限点原样复用，迁移按 `migrations` 已执行记录跳过，不重复建表、不清数据。

### 十一·3 禁用 / 启用 / 回滚 / 修复

- **禁用**（软拔）：停门禁、卸路由/事件/任务，保留文件、数据、权限点；`runtime.overrides[key]=false`。
- **启用**（软插）：清 override、重新挂载、重注册事件/任务。
- **回滚**：恢复 `.backup` 最近版本并重新挂载；若旧版不兼容新 schema（健康检查失败），保留新 schema 并标记 `rollback_blocked`，不强行降级。
- **修复**：重新扫描 → 跑缺失迁移 → 补权限 → 重新挂载 → 健康检查。用于手工删目录、迁移中断、权限丢失。

### 十一·4 迁移 v2

```text
migrations.sql               # 新装：只允许 CREATE TABLE IF NOT EXISTS / 安全索引 / 种子
migrations/0002_add_xxx.py   # 存量升级：apply(db, ctx)，ctx 提供 add_column_if_missing 等
migrations/0003_backfill.py
```

- 每个文件执行前校验 SHA256，已执行文件被篡改 → 阻止启动并标记 `broken`。
- 每个扩展独立 try/except，一个失败不阻塞后续扩展；失败写 registry/health，不挂载新版本。
- 只允许扩展式变更：新列可空、不删列、不改类型；破坏性清理放到下一个小版本。
- 记录落 `.state/schema.json`（不新增核心表）；旧 `migrations.sql` 的 `mtime:size` 指纹继续保留兼容。

### 十一·5 API 面

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/admin/market/apps` | 目录 + 已购 + 已装 + 健康 + 可更新 |
| POST | `/admin/market/apps/{key}/install` | 安装/更新，返回 action/from/to/health/rollback |
| POST | `/admin/market/apps/{key}/uninstall` | keep/purge，purge 需 `confirm_key` |
| POST | `/admin/market/apps/{key}/enable` | 软插 |
| POST | `/admin/market/apps/{key}/disable` | 软拔 |
| POST | `/admin/market/apps/{key}/rollback` | 回滚最近备份 |
| POST | `/admin/market/apps/{key}/repair` | 修复迁移/权限/挂载 |
| GET | `/admin/market/lifecycle/logs` | 审计日志（`.state/lifecycle.jsonl`） |
| GET | `/admin/extensions` | 合并 registry 的 version/health/data_policy/worker_restart_required |

以上全部要求 `setting.manage` 权限，并注入操作人写审计。

### 十一·6 前端与 worker

- 安装/更新/卸载/清除/启停/回滚/修复后统一 `await auth.fetchMe(); await reloadExtensions(); await fetchApps()`，解决权限缓存导致菜单不出现。
- 卸载后若当前路由属于该 key → `router.replace('/market')`。
- Web 进程热生效；Celery worker/beat 是独立进程，操作后返回 `worker_restart_required=true`，UI 明示「后台任务需重启 worker 后生效」；多 worker 同上，不假装热生效。

### 十一·7 自检命令

```bash
cd /www/wwwroot/mes-extensions && python3 pack.py --check                        # 打包闸门
cd /www/wwwroot/mes-extensions && python3 _selftest/lifecycle_check.py --host    # 宿主契约自检
cd /www/wwwroot/cenkormes/backend && .venv/bin/python -m pytest tests/test_extension_lifecycle.py -q
```

`pack.py v2` 额外校验：manifest v2 必填/命名空间/`data.tables` 命名/依赖格式、`migrations/` 版本连续且静态拒绝 `DROP/TRUNCATE/RENAME/ALTER DROP/MODIFY`、`frontend/plugin.js` 通过 `node --check`、README 恰好 10 节、zip 内无 `.bak/.pyc/__pycache__/.git`。
