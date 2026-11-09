# CenkorMES 拓展应用：开发 → 上传 → 审核 → 安装 → 卸载 全流程

> 2026-11-09 整理。本文按当前代码核实编写（非设计稿），覆盖三个系统：
> **mes-extensions**（扩展源码与打包）、**cenkor-admin**（hub/应用中心，portal.cenkor.cn）、
> **cenkormes**（实例/宿主）。权威实现：
> `cenkormes/backend/app/extension_host/lifecycle.py`、
> `cenkor-admin/backend/src/cenkor_admin/apps/system/store_router.py`、
> `mes-extensions/pack.py`。
> 配套阅读：`docs/EXTENSIONS.md`（宿主与开发指南）、`docs/EXTENSION_LIFECYCLE.md`（插拔闭环 v2）。

## 0. 全景图

```
开发者                          平台（hub）                        客户实例
──────                          ──────────                        ────────
mes-extensions/<key>/           cenkor-admin (8002)
  │ pack.py 打包+闸门              │ POST /submissions (zip)
  └── <key>-<ver>.zip ──────────> │ app_submissions: pending
                                  │ POST /submissions/{id}/review
                                  │   approve → approved（可分发）
                                  │   reject  → rejected
                                  │ POST /publish / yank（上架/撤回）
                                  │
                                  │ GET cloud/packages/{key}?license_key=
                                  │   <──────── zip ────────────────> cenkormes 实例
                                  │                                    │ POST /admin/market/install
                                  │                                    │   preflight→stage→migrate
                                  │                                    │   →backup→swap→activate→health
                                  │                                    │ hot 生效（单进程，无需重启）
```

三个关键词先记住：

- **审核与上架分离**：`approved` ≠ 可被目录看到；`published_at` 有值且未被 `yank` 才进目录。
- **审核与安装权限分离**：审核是 `app.store.review` / `store:review`；实例侧安装/卸载等一律 `setting.manage`。扩展是任意 Python，**不做沙箱**，安全靠人工审核 + 权限命名空间 + SHA256。
- **重打包 ≠ 发布**：hub 的 `app_submissions` 里没有对应版本行，实例永远显示「已是最新」。

## 1. 开发

### 1.1 包结构（5 件套，参考 `mes-extensions/TEMPLATE/`）

```
<key>/
├── manifest.json        # 清单（必填）
├── router.py            # 后端 API，前缀 /api/extensions/<key>
├── models.py            # 可选，SQLAlchemy 模型
├── migrations.sql       # 新装建表（只允许加法，见 1.3）
├── migrations/          # 可选，存量升级 0002_xxx.py（apply(db, ctx)）
├── frontend/plugin.js   # 可选，admin 前端插件
└── README.md
```

### 1.2 manifest.json（v2 契约，强校验）

```json
{
  "key": "stock_safety",
  "name": "安全库存预警",
  "version": "1.0.0",
  "manifest_version": 2,
  "schema_version": 1,
  "min_core_version": "2.2.0",
  "product": "cenkormes",
  "permissions": [
    {"code": "ext.stock_safety.view", "name": "查看"},
    {"code": "ext.stock_safety.manage", "name": "管理"}
  ],
  "menus": [
    {"title": "安全库存", "path": "/ext/stock_safety", "icon": "Warning", "permission": "ext.stock_safety.view"}
  ],
  "data": {
    "retention": "ask",
    "tables": [
      {"name": "ext_ss_rules", "mode": "own"},
      {"name": "stocks", "mode": "read"}
    ],
    "files": []
  },
  "tasks": {"celery": [], "beat": []},
  "dependencies": [],
  "changelog": "首版"
}
```

硬性规则（`manifest.py` 校验，违反直接拒装）：

| 项 | 规则 |
|---|---|
| key | `^[a-z][a-z0-9_]{1,63}$`，与目录名一致 |
| version | semver（v2 强制） |
| 权限码 | 必须落在 `ext.<key>.` 命名空间内 |
| 菜单路径 | 必须以 `/ext/` 开头 |
| data.retention | 只允许 `keep` / `ask` |
| data.tables[].mode | 只允许 `own` / `read` / `write` |
| min_core_version | 不得高于当前实例 `VERSION` |

v1 老包仍可装（缺省兜底），新包与升级包必须 v2。

### 1.3 迁移铁律：只做加法

实例侧迁移指纹是 `mtime:size`，**任何一次重装都会重跑 `migrations.sql`**，所以包内 SQL
只能出现这些形态（`pack.py` 静态闸门拦截）：

- ✅ `CREATE TABLE IF NOT EXISTS` / `CREATE [UNIQUE] INDEX IF NOT EXISTS` / guarded `INSERT`
- ❌ `DROP` / `TRUNCATE` / `RENAME` / `ALTER ... DROP|MODIFY` / `CREATE`（缺 IF NOT EXISTS）
- ❌ `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`——这是 MariaDB 语法，MySQL 8.0 直接 1064
  （存量库加列写进 `migrations/0002_xxx.py`，用 ctx 的 `add_column_if_missing`，底层查
  `information_schema`，不写 MySQL 不支持的语法）

破坏性清理延后一个小版本、走平台运维脚本，永远不进包。

### 1.4 事件钩子（可选）

两种钩子：notify（通知型，失败不影响主流程）/ intercept（拦截型，fail-open、只读、有超时预算）。
事件契约表 28 个事件名**只增不改**，订阅用 `register_events` 约定，
可视化在 admin「事件钩子」页（`/api/admin/extensions/events/*`）。

### 1.5 本地调试（不接应用中心）

```bash
cp -r backend/extensions_samples/quotation_demo backend/extensions/my_ext
# 改 manifest.json（key 与目录名一致）与 router.py / plugin.js
# 重启后端（本地模式自动加载）
python backend/scripts/extension.py list
```

注意路由前缀是 `/api/extensions/<key>/...`（写成 `/api/admin/extensions/...` 一律 404）；
扩展路由不进 openapi，找不到就 grep `@router.get`。

## 2. 打包与自检（mes-extensions）

```bash
cd /www/wwwroot/mes-extensions
python3 pack.py --check [key]      # 体检：源码/zip/manifest/迁移闸门，全绿才继续
python3 pack.py --build <key>      # 重新打包单个包
python3 pack.py --publish-hint     # 打印发布顺序与校验命令
```

自检另有 `_selftest/lifecycle_check.py`（宿主生命周期）与
`_selftest/manifest_check.py`（manifest 契约），发版前都跑一遍。

## 3. 上传（hub 侧 cenkor-admin）

### 3.1 开发者身份

- 必须用**门户（portal）账号**，且已注册为开发者（`app_developers`，active 状态）；
  admin 后台 token 不能提交（两个身份空间互不相干，这是故意的防归属错乱设计）。

### 3.2 先体检再提交

```http
POST /submissions/precheck      # multipart: file, app_key, product, dev_method
```

返回 manifest 摘要 + 迁移静态扫描 + 包 SHA256。与 submit 用同一套校验函数，
「precheck 绿了但提交 400」不会发生。

### 3.3 正式提交

```http
POST /submissions               # multipart: file(zip), app_key, name, version,
                                #   description, category, product, dev_method,
                                #   pricing(可选), changelog
```

服务端闸门（按顺序）：

1. zip 后缀 + 大小上限（超限 413）；
2. `app_key` 格式 / `version` 格式（防路径穿越）；
3. `product` / `dev_method` 白名单（cenkormes 扩展：`product=cenkormes`、`dev_method=extension`）；
4. **查重在落盘之前**：同 `(product, app_key, version)` 已存在 → 409（否则会先把磁盘包
   覆盖掉，让老 approved 行的 file_path/file_hash 失真）；
5. version 必须 semver，且与已装版本比较。

落盘：`uploads/apps/<app_key>-<version>.zip`，`app_submissions.status = pending`。

### 3.4 平台自营直发（开发者即平台时）

不必走门户表单，用发布脚本（默认 dry-run）：

```bash
PY=/www/server/pyporject_evn/cenkor/bin/python
cd /www/wwwroot/cenkor-admin/backend
$PY scripts/publish_extension.py --keys mold_management            # 干跑
$PY scripts/publish_extension.py --keys mold_management --apply    # 真发布
```

它先调 `pack.py` 体检，再只新增 `app_submissions` 版本行（永不改删别的版本行；
同版本同 hash 幂等跳过；product 轴继承该 app_key 现有最新行的基线信息）。
注意：**DSN 优先取正在服务的 8002 进程环境**，`.env` 可能指向别处的库。

## 4. 审核（hub 管理后台）

| 接口 | 权限 | 作用 |
|---|---|---|
| `GET /submissions/{id}/review-bundle` | `app.store.review` / `store:review` | 审核材料：manifest 契约 + 权限/菜单清单 + 迁移静态扫描 + 包指纹（落盘后被替换能当场发现） |
| `POST /submissions/{id}/review` | 同上 | `action=approve/reject` + `note`，写 `reviewed_by/reviewed_at` |
| `POST /submissions/batch-review` | 同上 | 批量；只对 `pending` 生效，其余进 `skipped`（部分成功语义） |
| `POST /submissions/{id}/publish` | 同上 | 审核通过后再上架（写 `published_at`） |
| `POST /submissions/{id}/yank` | 同上 | 撤回：只阻止新下载/新安装，**已装实例不受影响** |

审核页人工核查清单（不看代码等于没审——扩展是任意 Python）：

1. review-bundle 里的迁移扫描有没有 BLOCK 项；
2. 权限码是否越出 `ext.<key>.` 命名空间、相比上一版是否悄悄加权限；
3. router.py 里有没有碰其他扩展/核心表、外发请求、执行动态代码；
4. `data.tables` 声明与 migrations.sql 实际建表是否一致；
5. 包指纹（SHA256）与提交时一致。

**可分发判定**：`status ∈ (approved, published, installed)` 且未 yank。
hub 的 `cloud/packages/{app_key}` 就是按 `product + 这个状态筛选取最新一条`。

## 5. 实例侧安装（cenkormes）

### 5.0 一次性：实例绑定与授权

```
PUT  /admin/market/hub                # 配 hub 地址（存 platform_settings.market_hub_url）
POST /admin/market/bind/start         # 拿设备码
→ 门户 portal.cenkor.cn/connect 确认
GET  /admin/market/bind/poll          # 换发长期 instance_token（Bearer，落 platform_settings）
```

授权模型：`GET cloud/my-purchases`（Bearer）拉已购列表，每项含 `license_key`；
`POST licenses/{license_key}/activate`（instance_fp）激活绑定。
web 进程内 daemon 线程**每 15 分钟**刷一次快照（`ENTITLEMENT_SYNC_MINUTES`），
打开市场页也会顺手刷；hub 不可达时保留上次快照（fail-open，不误停正在跑的扩展），
吊销/过期在下一轮心跳生效。

### 5.1 安装入口

- 页面：admin「功能市场」`/market`（MarketPage.vue）；
- API：`POST /admin/market/install` 或 `/admin/market/apps/{key}/install`，
  权限 `setting.manage`，需要已持有该 app 的有效 license_key。

### 5.2 流水线（热生效，无需重启）

```
preflight → stage → backup → migrate → swap → activate → health → registry/audit
```

| 阶段 | 关键动作 | 失败处理 |
|---|---|---|
| preflight | zip 合法性、成员白名单（拒 `..`/绝对路径/符号链接/`__MACOSX`/`.git`/`node_modules`/`.pyc`）、key 匹配、manifest 校验、product/核心版本/依赖/表冲突、SHA256 | 400/409，目录零改动 |
| stage | 解压到 `extensions/.staging/<key>-<ver>-<uuid>/`，不碰 live | 删 staging，旧版继续服务 |
| backup | 旧目录复制到 `.backup/<key>/<ver>-<ts>/`，保留最近 3 份 | 失败即终止 |
| migrate | 只跑该扩展的新迁移 | 删 stage，旧版继续服务 |
| swap | `os.replace` 两步：live→backup，stage→live | 第二步失败立即换回 |
| activate | 同步权限（事务可回滚）→ 挂路由 → 注册事件/任务 → 写 registry | 走 rollback |
| health | import、路由数>0、声明表存在、迁移记录完整、plugin.js 可取、权限点存在、可选 `lifecycle.healthcheck()` | 标 broken / 回滚 |

不变量：live 目录永远是完整可运行版本，不存在「删一半」的中间态；
`.staging` 不被扫描不进 registry；任何失败都写 `last_error` 并审计，不吞异常。
写操作串行：进程内 `threading.Lock` + `fcntl.flock(.state/lifecycle.lock)`。

版本语义：同版本同 SHA → 409「已是最新」；同版本不同 SHA → 拒绝覆盖（请提升版本号）；
降级需显式 `allow_downgrade=true`。

### 5.3 装完之后

- 单进程 uvicorn：路由/菜单/权限立即热生效，前端刷新即可（MarketPage 统一
  `fetchMe + reloadExtensions + fetchApps`，避免权限缓存）；
- **多 worker**（`WEB_CONCURRENCY`/`--workers`>1）：返回 `multi_worker=true`，需重启全部 worker；
- **Celery**：任务注册在独立进程，安装/更新含 `tasks` 的包后返回
  `worker_restart_required=true`，UI 明示「后台任务需重启 worker 后生效」；
- 状态记录：`extensions/.state/registry.json`（版本/健康/表清单/备份路径）；
  审计流水 `.state/lifecycle.jsonl`（5MB 轮转留 5 份）。

## 6. 更新 / 启停 / 回滚 / 修复

| 操作 | API | 语义 |
|---|---|---|
| 更新 | `POST /admin/market/apps/{key}/install` | 同一条安装链路；`from_version`/`to_version`/`package_sha256` 全审计 |
| 禁用（软拔） | `POST .../disable` | 卸路由/事件/任务，**保留文件与数据**，写 `overrides[key]=disabled` |
| 启用（软插） | `POST .../enable` | 清 override → 重新挂载 → 健康检查 |
| 回滚 | `POST .../rollback` | 恢复最近备份 + 旧版重挂 + 权限快照恢复；旧版不兼容新 schema 时置 `rollback_blocked` 不强降 |
| 修复 | `POST .../repair` | 幂等：重扫描 → 补缺失迁移 → 补权限 → 重挂 → 健康检查。外部手删目录、迁移中断都用它收敛 |

## 7. 卸载

```http
POST /admin/market/apps/{key}/uninstall
# body: { "app_key": "stock_safety", "purge": false, "confirm_key": "" }
```

固定顺序（`lifecycle.uninstall`）：

1. `runtime.retiring.add(key)` → 新请求 503，等待 2 秒排空；
2. 热卸路由 / 事件订阅 / Celery 任务（失败只记 `worker_restart_required=true`，不假装成功）；
3. 删 `role_permissions` 中 `ext.<key>.*` 绑定及权限点（不碰其他前缀）；
4. 清 `sys.modules` 子树、`app.state` 缓存、overrides；
5. live 目录移入 `.trash/<key>-<ts>/`（不直接删）；
6. 数据策略二选一：
   - **keep（默认）**：表/文件/权限记录保留，registry 记 `uninstalled_keep`，
     **重装后数据原样恢复、迁移不重复跑**；
   - **purge（彻底清除）**：必须 `purge=true` 且 `confirm_key=<key>` 精确匹配。
     先把 own 表导出为 JSONL 到 `data/.purge_backups/<key>-<ts>/`（导出失败默认终止），
     再按依赖逆序 DROP，最后删 `data/<key>/` 与 state。own 表来源 =
     manifest `mode=own` ∪ `migrations.sql` 的 CREATE TABLE，减去核心表与其他扩展的表
     （denylist 双重保护）。**不可逆**。

依赖保护：被其他已装扩展依赖的 key 拒绝卸载（409），先卸依赖方。

## 8. 排查速查

| 现象 | 先看 |
|---|---|
| 市场页「可更新 N 个」永远 0 | hub `app_submissions` 有没有新版行（重打包 ≠ 发布）；用 `publish_extension.py --apply` |
| 装不上：包级 400/409 | preflight 报错原文；`pack.py --check` 本地先跑 |
| 装完菜单不出现 | 权限缓存：市场页操作后统一 `fetchMe + reloadExtensions`；多 worker 需重启 |
| 扩展路由 404 | 前缀必须是 `/api/extensions/<key>/...`；扩展路由不进 openapi |
| 事件没触发 | `/api/admin/extensions/events/recent` 与 `/events/stats`（环形缓冲，重启清零） |
| 状态异常 broken | `GET /admin/market/lifecycle/logs` 看审计；`repair` 收敛 |
| 迁移报 1064 | 包里写了 `ADD COLUMN IF NOT EXISTS`（MariaDB 语法）；存量库加列走 `migrations/000N.py` |
| 数据「丢了」 | 卸载选了 keep 的话表还在；查 registry 的 data_policy 与 trash 路径 |

## 9. 命令速查

```bash
# 打包侧（mes-extensions）
python3 pack.py --check && python3 pack.py --build <key>

# hub 侧发布（平台自营）
cd /www/wwwroot/cenkor-admin/backend
/www/server/pyporject_evn/cenkor/bin/python scripts/publish_extension.py --keys <key> --apply

# 发布后校验（x-app-version / x-app-product）
curl -sI "https://portal.cenkor.cn/api/v1/store/cloud/packages/<key>?license_key=<LIC>" \
  | grep -iE 'x-app-(version|product)'

# 实例侧生命周期测试（不执行安装、不重启服务）
cd /www/wwwroot/cenkormes/backend
/www/server/pyporject_evn/cenkormes/bin/python -m pytest tests/test_extension_lifecycle.py -q

# 前端自检
cd /www/wwwroot/cenkormes/frontend-admin-pro
npm run check && npm run check:ext-routes
```

## 10. 已知边界

- 扩展是任意 Python，**不做沙箱**；安全 = 人工审核 + 权限命名空间 + SHA256 + 权限分离。
- MySQL DDL 隐式提交：迁移只做加法，回滚依赖旧代码兼容新 schema。
- 多 worker / Celery worker 的热生效是假象，必须人工重启（返回值里明确标了）。
- hub 不可达时授权快照 fail-open（不误停正在运行的扩展）；吊销/过期下一轮心跳（≤15 分钟）生效。
- 彻底清除不可逆：JSONL 备份 + 输入 key 确认 + own 表白名单 + 核心表 denylist 四重防线。
