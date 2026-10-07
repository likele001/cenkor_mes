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
| `loader.py` | `mount_extensions()` 路由挂载 + `require_extension` 授权门控 |
| `sync.py` | 心跳同步线程（标准库 urllib 实现，无第三方依赖） |
| `host.py` | 启动装配（`mount_all` / `startup_host`）与扩展权限注入（补授 admin） |

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
