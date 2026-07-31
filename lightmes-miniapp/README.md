# LightMes 微信小程序 (uni-app)

Vue 3 + TypeScript + Pinia + uni-app，覆盖完整员工端与 PC 租户管理端全量功能。

**工程绝对路径（Linux 服务器）：** `/www/wwwroot/lightmes/lightmes-miniapp`  
所有 `npm` 命令都在这个目录里执行，不要在 `backend`、`frontend-admin-pro` 里执行。

---

## 推荐流程：先在服务器 npm build，再拷到 Windows

### 第一步：SSH 登录服务器，进入目录

```bash
cd /www/wwwroot/lightmes/lightmes-miniapp
pwd
# 应输出：/www/wwwroot/lightmes/lightmes-miniapp
```

### 第二步：安装依赖（仅第一次或 package.json 变更后）

```bash
npm install
```

> 会在本目录生成 `node_modules/`，**不要**拷到 Windows。

### 第三步：确认生产 API 地址（改域名必做）

编辑 `.env.production`，例如：

```env
VITE_API_BASE_URL=https://admin.lightmes.user.023ent.net/api
```

### 第四步：构建微信小程序

```bash
npm run build:mp-weixin
```

成功时末尾会有：`DONE  Build complete`，并生成目录：

```text
/www/wwwroot/lightmes/lightmes-miniapp/dist/build/mp-weixin/
├── app.json          ← 微信工具必须有这个文件
├── app.js
├── project.config.json
└── pages/ ...
```

自检：

```bash
ls -la /www/wwwroot/lightmes/lightmes-miniapp/dist/build/mp-weixin/app.json
```

### 第五步：打包拷到 Windows（只拷构建结果）

在服务器上打 zip（体积小，不含 node_modules）：

```bash
cd /www/wwwroot/lightmes/lightmes-miniapp/dist/build
zip -r ~/mp-weixin.zip mp-weixin
ls -lh ~/mp-weixin.zip
```

用 **WinSCP / FTP / 宝塔文件** 把 `mp-weixin.zip` 下载到 Windows，解压得到文件夹 `mp-weixin`。

### 第六步：微信开发者工具（Windows）

1. 打开「微信开发者工具」→ **导入项目**
2. 目录选解压后的 **`mp-weixin`**（里面有 `app.json` 的那一层）
3. AppID：`wxccf32ba082446a3d`（与 `src/manifest.json` 一致）
4. 公众平台 → 开发设置 → **request 合法域名**：`admin.lightmes.user.023ent.net`

> 以后只改 `.env.production` 或业务代码：在服务器重复 **第四步 build** → 重新下载 zip → 微信工具里重新打开/编译。

---

## 拷贝清单（容易搞错）

| 路径 | 拷到 Windows？ |
|------|----------------|
| `node_modules/` | **否** |
| `src/` | 仅当你在 Windows 自己改代码时才要 |
| `dist/build/mp-weixin/` | **是（推荐只拷这个）** |
| 整个 `lightmes-miniapp/` | 可以，但必须已 build，且**不要带** `node_modules` |

---

## 本机开发命令（可选）

```bash
cd /www/wwwroot/lightmes/lightmes-miniapp
npm run dev:mp-weixin    # 开发，输出 dist/dev/mp-weixin
npm run build:mp-weixin  # 发布，输出 dist/build/mp-weixin
```

**微信开发者工具导入目录：**

1. 直接导入 `dist/build/mp-weixin`（最简单）
2. 或导入 `lightmes-miniapp` 根目录（依赖根目录 `project.config.json` 的 `miniprogramRoot`，且必须先 build）

不要只导入 `src/`，会报「未找到 app.json」。

### 常见报错

| 报错 | 原因 | 处理 |
|------|------|------|
| 未找到 `app.json` | 未 build 或导错目录 | 先 `npm run build:mp-weixin`，再导入 `dist/build/mp-weixin` |
| `custom-tab-bar/index.wxml` not found | 旧包里有 `index.vue` 未编译 | 服务器重新 build 后，**整包替换** Windows 上的 `mp-weixin`，不要只覆盖部分文件 |

`custom-tab-bar` 必须使用微信原生 `index.wxml/js/wxss`（已在 `src/custom-tab-bar/`），不能用 `.vue`。

`.gitignore` 已忽略 `node_modules/` 和 `dist/`。

## 配置

- `.env.development` / `.env.production`：`VITE_API_BASE_URL` 指向后端 `/api`
- `src/manifest.json` → `mp-weixin.appid` 填写小程序 AppID
- 后端配置 `WX_MINIAPP_APPID`、`WX_MINIAPP_SECRET`

## 架构

- **主包**：登录、角色分流、5 个 Tab 壳页（员工/管理双模式）
- **分包 pages-employee**：报工、任务详情、工资、消息等
- **分包 pages-admin**：对齐 `frontend-admin-pro` 全部管理模块（56 页）
- **权限**：`GET /auth/me` 返回 `roles` + `permissions`；管理 API 自动带 `X-LightMes-Portal: admin`

详见 [`docs/小程序方案.md`](../docs/小程序方案.md)。
