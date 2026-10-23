# 扩展全生命周期（插拔闭环 v2）

本文是扩展「安装 → 更新 → 回滚 → 禁用 → 启用 → 卸载 → 彻底清除 → 修复」的唯一权威说明。
配套文档：`docs/EXTENSIONS.md`（宿主接入、事件钩子、开发流程）、`backend/app/extension_host/lifecycle.py`（实现）。

## 1. 状态机

```text
available ──install──> installing ──ok──> installed_enabled
                            └──fail──> rollback_to_previous
installed_enabled ──update──> updating ──ok──> installed_enabled(new)
                            └──fail──> rollback_to_previous
installed_enabled ──disable──> installed_disabled
installed_disabled ──enable──> installed_enabled
installed_* ──uninstall──> uninstalling ──ok──> uninstalled_keep / uninstalled_purged
any ──health_fail──> broken ──repair──> installed_enabled
```

不变量（任何操作都必须成立）：

1. live 目录永远是完整可运行的版本，不存在「删一半」的中间态。
2. `.staging` 不被扫描、不被挂载、不进 registry。
3. 迁移成功前不换入新版本；换入失败立即把备份换回。
4. 卸载先停门禁（`require_extension` 返回 503）并排空请求，再卸路由/事件/任务。
5. 任何失败都写 `last_error` 与回滚结果，不吞异常。
6. 写操作串行：进程内 `threading.Lock` + `fcntl.flock(.state/lifecycle.lock)`。

## 2. Manifest v2 契约

```json
{
  "key": "stock_safety",
  "name": "安全库存预警",
  "version": "1.0.0",
  "schema_version": 1,
  "manifest_version": 2,
  "min_core_version": "2.2.0",
  "product": "cenkormes",
  "permissions": [{"code": "ext.stock_safety.view", "name": "查看"}],
  "menus": [{"title": "安全库存", "path": "/ext/stock_safety", "icon": "Warning", "permission": "ext.stock_safety.view"}],
  "data": {
    "retention": "ask",
    "tables": [
      {"name": "ext_ss_rules", "mode": "own"},
      {"name": "stocks", "mode": "read"}
    ],
    "files": []
  },
  "tasks": {"celery": ["stock_safety.scan"], "beat": ["stock_safety.scan.every_5m"]},
  "dependencies": []
}
```

宿主强校验（`extension_host/manifest.py`）：

- `key` 匹配 `^[a-z][a-z0-9_]{1,63}$`；`version` 必须 semver；`min_core_version` 不高于当前 `VERSION`。
- 权限码必须以 `ext.<key>.` 开头；菜单路径必须以 `/ext/` 开头。
- `data.retention ∈ {keep, ask}`；`data.tables[].mode ∈ {own, read, write}`。
- `tasks.celery` / `tasks.beat` 必须是数组；`dependencies[].key` 必须存在。
- v1 老包继续可装（缺省值兜底），新包与升级包必须 v2。

## 3. 迁移 v2

```text
migrations.sql              # 新装：只允许 CREATE TABLE IF NOT EXISTS / 安全索引 / guarded INSERT
migrations/0002_add_xxx.py  # 存量升级：apply(db, ctx)
migrations/0003_backfill.py
```

- `ctx` 提供 `add_column_if_missing(table, column, ddl)`、`create_index_if_missing(...)`、
  `create_table_if_missing(...)`、`drop_index_if_exists(...)`；底层查 `information_schema`，
  不写 `ALTER ... ADD COLUMN IF NOT EXISTS`（MySQL 8.0 不支持）。
- 每个文件执行前校验 SHA256；已执行文件被篡改 → 阻止启动并标记 `broken`。
- 每个扩展独立 try/except：一个失败不阻塞其他扩展，失败写 registry/health，且不挂载新版本。
- 只允许「扩展式」变更：新列可空、不删列、不改类型；破坏性清理延后一个小版本。
- 记录落 `.state/schema.json`（key → `[{version, filename, checksum, applied_at}]`），不新增核心表。
- `pack.py` 静态拦截 `DROP/TRUNCATE/RENAME/ALTER DROP/MODIFY` 与裸 `ALTER ADD`。

## 4. 安装 / 更新流水线

```text
preflight → stage → backup → migrate → swap → activate → health → registry/audit
```

| 阶段 | 关键动作 | 失败处理 |
|---|---|---|
| preflight | key 正则、manifest v2、product、semver、核心版本、依赖、包 SHA256、zip 成员白名单、路由/菜单/权限/表冲突 | 400/409，目录零改动 |
| stage | 解压到 `extensions/.staging/<key>-<version>-<uuid>/`；拒绝 `..`、绝对路径、符号链接、`__MACOSX`、`.git`、`node_modules`、`.pyc`；限制大小与文件数 | 删 staging，旧版继续服务 |
| backup | 旧目录复制到 `extensions/.backup/<key>/<version>-<ts>/`，保留最近 3 份 | 备份失败即终止 |
| migrate | 只跑该扩展的新迁移 | 删 stage，旧版继续服务 |
| swap | `os.replace(live, backup)` 再 `os.replace(stage, live)` | 第二步失败立即换回 backup |
| activate | 同步权限（可回滚事务）→ 挂载路由 → 注册事件/任务 → 写 registry | 走 rollback |
| health | import 成功、路由数 > 0、声明表存在、迁移记录完整、`plugin.js` 可获取、权限点存在、可选 `lifecycle.healthcheck()` | 标记 broken / 回滚 |

版本语义（`extension_host/version.py` 统一 semver）：

- 同版本同 SHA：409「已是最新」；同版本不同 SHA：拒绝并告警。
- 降级需显式 `allow_downgrade=true`。
- 更新成功后 `from_version` / `to_version` / `package_sha256` 全部写审计。

## 5. 卸载与彻底清除

固定顺序：

1. `runtime.retiring.add(key)`：`require_extension` 对新请求返回 503，等待 2 秒排空。
2. 从 `app.router.routes` 移除路由；`event_bus.unsubscribe_extension(key)`。
3. 按 manifest `tasks.celery` 从 Celery 注册表移除；删除 `beat_schedule` 中该 key 的条目；
   失败只记 `worker_restart_required=true`（不假装成功）。
4. 删除 `role_permissions` 中 `ext.<key>.*` 的绑定，再删同名 `permissions` 权限点；写审计；不碰其他前缀。
5. 清 `sys.modules` 子树（`cenkormes_ext_<key>*`）、`app.state` 缓存、`runtime.overrides[key]`。
6. 目录移入 `.trash/<key>-<ts>/`；`scan_extensions` 跳过点目录。
7. 数据策略：`keep` 保留表/文件/权限点记录；`purge` 走备份 + DROP。
8. 写 registry `uninstalled_keep` / `uninstalled_purged` 与审计，返回移除数量、数据保留清单、trash 路径。

彻底清除（purge）：

- 请求体必须带 `confirm_key=<key>` 且 `purge=true`，权限 `setting.manage`。
- 先导出 own 表到 `data/.purge_backups/<key>-<ts>/`（JSONL），导出失败默认终止。
- own 表来源 = manifest 声明 `mode=own` ∪ `migrations.sql` 的 `CREATE TABLE`，
  减去核心 `Base.metadata.tables` 与其他已装扩展的表（denylist 双重保护）。
- 按依赖逆序 DROP，最后删 `data/<key>/` 与 state 记录；保留 purge 审计。
- 表名前缀只是规范（新包要求 `ext_<key>_` / `<key>_`），purge 安全不依赖前缀，依赖白名单。

## 6. 启用 / 禁用 / 回滚 / 修复

| 操作 | 语义 | 失败处理 |
|---|---|---|
| disable（软拔） | 清门禁 → 卸路由/事件/任务 → 保留文件与数据 → 写 `overrides[key]=disabled` | 回滚挂载 |
| enable（软插） | 清 `overrides[key]` → 挂载路由 → 注册事件/任务 → 健康检查 | 重新标记 disabled |
| rollback | 恢复最近备份目录 → 重新挂载旧版 → 恢复权限快照 → 重注册旧事件/任务 | 旧版不兼容新 schema 时置 `rollback_blocked`，不强行降级 |
| repair | 重新扫描 → 跑缺失迁移 → 补权限 → 重新挂载 → 健康检查 | 写 health 与 last_error |

外部手工删目录、迁移中断、权限丢失，都用 repair 收敛；repair 是幂等的。

## 7. 权限、任务与 worker

- 安装/更新/卸载/清除/禁用/启用/回滚/修复全部要求 `setting.manage`，并注入 `user` 写审计。
- 安装时 license 已校验通过则对该 key 强制跑迁移与权限同步，不再依赖尚未刷新的授权快照；
  安装完成后异步刷新 `my-purchases`。
- 权限命名空间由 `manifest.py` 强制，冲突权限码拒绝安装。
- Web 进程热生效；Celery worker/beat 是独立进程，安装/更新/卸载后返回
  `worker_restart_required=true`，UI 明示「后台任务需重启 worker 后生效」。
- 检测到 `WEB_CONCURRENCY` / `--workers` > 1 时返回 `multi_worker=true`，提示需重启全部 worker。

## 8. API 面

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/admin/market/apps` | 目录 + 已购 + 已装 + 健康 + 可更新 |
| POST | `/admin/market/apps/{key}/install` | 安装/更新，返回 action/from/to/health/rollback |
| POST | `/admin/market/apps/{key}/uninstall` | keep/purge，带 `confirm_key` |
| POST | `/admin/market/apps/{key}/enable` | 软插 |
| POST | `/admin/market/apps/{key}/disable` | 软拔 |
| POST | `/admin/market/apps/{key}/rollback` | 回滚最近备份 |
| POST | `/admin/market/apps/{key}/repair` | 修复迁移/权限/挂载 |
| GET | `/admin/market/lifecycle/logs` | 审计日志 |
| GET | `/admin/extensions` | 合并 registry 的 version/health/data_policy/worker_restart_required |

## 9. 前端生命周期

`frontend-admin-pro/src/utils/extensionLoader.ts`：

- 记录每个 key 的路由名、菜单、locale 顶层 key；提供 `unloadExtension(key)` /
  `reloadExtensions(): Promise<{loaded, failed}>`。
- `resetExtensions` 清动态路由、菜单、注册缓存与该 key 的 locale 命名空间。
- 暴露 `hasExtensionRoute(path)` 与 `isExtensionRouteActive(key)`，供卸载后跳转。

`views/market/MarketPage.vue`：

- 安装/更新/卸载/清除/启用/禁用/回滚/修复后统一 `await auth.fetchMe(); await reloadExtensions(); await fetchApps()`，
  解决权限缓存导致菜单不出现。
- 卸载后若当前路由属于该 key，`router.replace('/market')`。
- 卸载弹窗二选一：保留数据（默认）/ 彻底清除（要求输入 key）。
- 卡片展示 installed_version / latest_version / health / last_operation / worker_restart_required。

## 10. 审计与 registry

`.state/registry.json`（单 key）：

```json
{
  "stock_safety": {
    "version": "1.1.0", "schema_version": 2, "previous_version": "1.0.0",
    "installed_at": "2026-10-22T10:00:00Z", "package_sha256": "…",
    "status": "installed_enabled", "health": {"ok": true, "checked_at": "…"},
    "tables": ["ext_ss_rules", "ext_ss_alerts"], "data_policy": "keep",
    "backup": ".backup/stock_safety/1.0.0-20261022T095900Z",
    "worker_restart_required": true, "last_error": null
  }
}
```

`.state/lifecycle.jsonl`：谁、何时、action、from→to、结果、耗时、包 SHA、数据策略；
5MB 轮转保留 5 份，`GET /admin/market/lifecycle/logs` 可读。

## 11. 测试矩阵与命令

`backend/tests/test_extension_lifecycle.py`（临时目录 + 隔离 DB + 合成扩展 v1/v2）：

| 场景 | 断言 |
|---|---|
| 非法 key/路径/zip 成员 | 400，extensions 目录无变化 |
| 缺依赖/核心版本不符 | 409/400，旧版仍可用 |
| 安装成功 | 目录、路由、权限、表、事件、菜单、健康全绿 |
| 更新成功 | 旧路由移除、新路由生效、数据保留、备份存在 |
| 更新失败 | 自动回滚，旧版路由/数据可用 |
| 卸载 keep | 路由 404、事件/任务/权限/模块清空，表与数据保留 |
| 重装 | 数据原样恢复，迁移不重复 |
| 卸载 purge | own 表删除，核心表不动，备份存在 |
| 依赖未卸 | 409，不允许卸载被依赖应用 |
| 并发安装 | 一个成功，一个 409/等待 |
| 外部删目录 | 启动标记 broken，repair 可恢复 |
| 当前路由卸载 | `scripts/check-extension-routes.mjs` 13 条断言：`hasExtensionRoute` / `isExtensionRouteActive` 在卸载后转 false，路由/菜单/locale 缓存回收干净 |

```bash
cd /www/wwwroot/cenkormes/backend
.venv/bin/python -m pytest tests/test_extension_lifecycle.py -q

cd /www/wwwroot/mes-extensions
python3 pack.py --check                    # 全量打包闸门
python3 pack.py --build <key>              # 单包重建
/www/wwwroot/cenkormes/backend/.venv/bin/python _selftest/lifecycle_check.py --host

cd /www/wwwroot/cenkormes/frontend-admin-pro
npm run check                              # vue-tsc 类型检查
npm run check:ext-routes                   # 前端生命周期 helper 自检（esbuild 现场打包真实 extensionLoader）
```

验证只跑 pytest / pack.py / node --check / 类型检查；不执行安装、不重启 uvicorn / celery。

## 12. 边界与已知限制

- MySQL DDL 隐式提交：迁移只做加法，回滚依赖旧代码兼容新 schema。
- 多 worker：默认单进程假设；检测到多 worker 返回 `multi_worker=true`，不假装热生效。
- Celery worker/beat：任务注册在独立进程，必须人工重启。
- 彻底清除不可逆：强制 JSONL 备份 + 输入 key + own 表白名单 + 核心表 denylist。
- 扩展是任意 Python，不做沙箱：靠人工审核、权限命名空间、SHA256、可选签名，审核与发布权限分离。
- 3D（`digital_twin`）先交付 2D，3D 只作渲染增强，不改表与 API。
