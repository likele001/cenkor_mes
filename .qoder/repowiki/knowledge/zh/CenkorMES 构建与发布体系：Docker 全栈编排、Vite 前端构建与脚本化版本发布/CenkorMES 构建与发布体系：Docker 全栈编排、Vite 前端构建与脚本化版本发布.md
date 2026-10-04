---
kind: build_system
name: CenkorMES 构建与发布体系：Docker 全栈编排、Vite 前端构建与脚本化版本发布
category: build_system
scope:
    - '**'
source_files:
    - backend/Dockerfile
    - docker/frontend/Dockerfile
    - docker-compose.yml
    - docker/scripts/entrypoint-api.sh
    - docker/scripts/init-demo.sh
    - start.sh
    - scripts/release-all.sh
    - VERSION
    - backend/requirements.txt
    - frontend-admin-pro/package.json
    - frontend-h5/package.json
    - lightmes-miniapp/package.json
---

## 1. 总体方案

CenkorMES 采用 **多仓库单体 + Docker Compose 一键编排** 的构建/部署模式，覆盖后端 Python(FastAPI)、管理端 Vue3(Vite)、H5 移动端 Vue3(Vite) 以及 uni-app 小程序四个产物。本地开发通过根目录 `start.sh` 统一拉起；生产环境通过 `docker-compose.yml` 一次性启动 MySQL 8.0、Redis 7、后端 API、Nginx 托管的管理后台与 H5 站点。

- 后端镜像：`backend/Dockerfile`（基于 `python:3.11-slim`，使用 PyMySQL 避免 gcc 编译链）
- 前端镜像：`docker/frontend/Dockerfile`（Node 20 构建 → Nginx 1.27-alpine 运行时，通过 `FRONTEND` 构建参数复用）
- 容器编排：`docker-compose.yml`（四服务 + 共享网络 `cenkormes` + 持久卷 `mysql_data`/`redis_data`/`storage_data`）
- 入口脚本：`docker/scripts/entrypoint-api.sh`（等待 MySQL 就绪 + 兜底生成 JWT_SECRET）
- 本地启动：`start.sh`（自动创建 `backend/venv`，dev 模式 uvicorn --reload + Vite dev server）
- 版本发布：`scripts/release-all.sh`（递增 `VERSION`、追加 `backend/CHANGELOG.json`、git commit/push）

## 2. 关键文件与职责

| 文件 | 职责 |
|---|---|
| `backend/Dockerfile` | 后端镜像：安装 `libgomp1`、pip 依赖、复制源码、暴露 8000 |
| `docker/frontend/Dockerfile` | 前端镜像：两阶段构建，按 `FRONTEND=frontend-admin-pro|h5` 选择源码与 nginx 配置 |
| `docker-compose.yml` | 定义 mysql / redis / backend / web-admin / web-h5 五服务及端口映射 |
| `docker/scripts/entrypoint-api.sh` | 容器入口：TCP 探测 MySQL 端口、prod 下兜底生成 JWT_SECRET |
| `docker/nginx/*.conf` | Nginx 反向代理：将 `/api` 转发到 `backend:8000`，静态资源由同容器提供 |
| `start.sh` | 本地一键启动：检测 venv、根据 `--prod` 切换 uvicorn reload 与 vite preview |
| `scripts/release-all.sh` | 版本发布：解析 `VERSION`，支持 `major/minor/patch` 递增，幂等更新 `CHANGELOG.json` |
| `VERSION` | 唯一版本号数据源（如 `v1.0.0`），格式为 `vMAJOR.MINOR.PATCH` |
| `backend/requirements.txt` | 后端 Python 依赖清单 |
| `frontend-admin-pro/package.json` | 管理端 Vite 脚本：`dev/build/preview/lint/check` |
| `frontend-h5/package.json` | H5 端 Vite 脚本（同上） |
| `lightmes-miniapp/package.json` | 小程序脚本：`dev:mp-weixin` / `build:mp-weixin` / `typecheck` |

## 3. 架构与约定

### 3.1 后端构建
- 基础镜像固定 `python:3.11-slim`，禁用字节码与 pip 缓存以减小体积。
- 数据库驱动强制使用纯 Python 的 PyMySQL（注释明确“无需 mysqlclient/gcc 编译链”），仅安装 `libgomp1` 作为 numpy/scipy/chromadb 的 OpenMP 依赖。
- pip 源通过 `PIP_INDEX_URL` 构建参数注入，默认官方源，国内可替换为清华源。
- 应用 CMD 固定为 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。

### 3.2 前端构建
- 两个 Web 前端（管理端、H5）共用同一 `docker/frontend/Dockerfile`，通过 `ARG FRONTEND` 在构建时选择源码目录与对应 nginx 配置文件。
- 构建阶段：`node:20-alpine` 执行 `npm ci --prefer-offline --no-audit --no-fund` 后 `npm run build`（先 `vue-tsc -b` 类型检查再 `vite build`）。
- 运行阶段：`nginx:1.27-alpine` 挂载 `dist` 到 `/usr/share/nginx/html`，并通过 `docker/nginx/${FRONTEND}.conf` 将 `/api` 反代到后端容器内部端口。
- 小程序（uni-app）独立于 Docker 流程，通过 `pnpm/yarn/npm run build:mp-weixin` 产出微信小程序包，不在本仓库中构建镜像。

### 3.3 容器编排
- `docker-compose.yml` 声明五服务：`mysql`(8.0, utf8mb4_unicode_ci)、`redis`(7-alpine)、`backend`、`web-admin`、`web-h5`。
- 所有服务加入共享网络 `cenkormes`，通过服务名互相访问（如 `backend:8000`）。
- 端口映射全部走 `.env` 变量：`APP_PORT`、`WEB_ADMIN_PORT`、`WEB_H5_PORT`，默认 8000/8080/8081。
- 依赖顺序：backend 依赖 mysql/redis 健康检查完成后再启动；web-* 依赖 backend。
- 数据持久化：`mysql_data`、`redis_data`、`storage_data` 三个命名卷。

### 3.4 启动与初始化
- 容器入口 `entrypoint-api.sh` 用 socket 探测 MySQL TCP 端口（最长 60 次 × 2s = 120s），失败则退出。
- prod 模式下若未设置安全的 `JWT_SECRET`，调用 `app.core.security.ensure_secure_jwt_secret()` 校验，不通过则临时生成随机密钥并告警。
- 建表与默认管理员由 FastAPI startup 事件根据 `DB_AUTO_CREATE`/`DB_AUTO_SEED` 环境变量触发，非 entrypoint 逻辑。

### 3.5 版本与发布
- 单一版本源：根目录 `VERSION` 文件（格式 `vX.Y.Z`）。
- `scripts/release-all.sh` 支持：
  - `VERSION_BUMP=major|minor|patch` 控制递增粒度（默认 patch）。
  - `--dry-run` 模拟执行，`--no-push` 仅本地提交。
  - 自动追加变更说明到 `backend/CHANGELOG.json`，按 `version` 字段幂等覆盖。
  - 最终 `git add` + `git commit -m "chore(release): bump version to ..."` + `git push -u origin <branch>`。
- 发布后需重启后端容器使 `system_versions` 表中的新版本生效（脚本末尾提示宝塔面板重启）。

## 4. 约定与约束

- **后端依赖必须来自 `backend/requirements.txt`**：Dockerfile 通过 `COPY backend/requirements.txt . && pip install -r requirements.txt` 安装，任何新增依赖需同步至此文件。
- **前端构建上下文必须是仓库根目录**：`docker/frontend/Dockerfile` 通过 `${FRONTEND}/package.json` 拷贝源码，因此 `docker compose build` 必须在仓库根执行。
- **端口可通过 `.env` 覆盖**：`APP_PORT`、`WEB_ADMIN_PORT`、`WEB_H5_PORT` 在 `docker-compose.yml` 中以 `${VAR:-default}` 形式引用，修改 `.env` 即可调整对外端口。
- **数据库连接字符串必须使用 PyMySQL 方言**：`DB_URL` 格式为 `mysql+pymysql://...`（见 docker-compose.yml 示例），因镜像不含 mysqlclient 编译依赖。
- **生产环境必须设置强 `JWT_SECRET`**：compose 注释要求 ≥32 位随机值，entrypoint 在 prod 下会兜底生成临时密钥但会输出警告。
- **版本号格式严格为 `vMAJOR.MINOR.PATCH`**：release 脚本通过 `${VER_NUM#*.}` 和 `${REST##*.}` 解析三段数字，不符合该格式的 VERSION 会导致递增逻辑异常。
- **CHANGELOG.json 按版本号幂等更新**：脚本先过滤掉同名 version 的记录再追加新条目，保证同一版本号只保留一份描述。
- **前后端 API 路径约定**：前端 nginx 配置将 `/api/*` 反代到后端 `backend:8000`，前端代码中请求路径均以 `/api` 前缀发起。
- **本地开发端口约定**：后端 8000、管理端 5174、H5 5173，可通过 `BACKEND_PORT`/`ADMIN_PORT`/`H5_PORT` 环境变量覆盖。

## 5. 缺失项说明

- 未发现 CI/CD 流水线配置（无 `.github/workflows`、`.gitlab-ci.yml`、Jenkinsfile 等）。
- 未发现 Makefile 或统一的顶层构建脚本（各子项目各自维护 package.json scripts）。
- 未发现跨平台交叉编译配置（Python 后端直接基于 x86_64 aarch64 的 python:slim 镜像）。
- 未发现独立的 lint/pre-commit 钩子配置（ESLint 仅在 frontend-* 的 package.json 中定义脚本）。
