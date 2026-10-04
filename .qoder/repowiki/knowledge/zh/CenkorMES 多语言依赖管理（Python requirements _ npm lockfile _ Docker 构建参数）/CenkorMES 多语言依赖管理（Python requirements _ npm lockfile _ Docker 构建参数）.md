---
kind: dependency_management
name: CenkorMES 多语言依赖管理（Python requirements / npm lockfile / Docker 构建参数）
category: dependency_management
scope:
    - '**'
source_files:
    - backend/requirements.txt
    - backend/requirements-pdf.txt
    - backend/Dockerfile
    - docker-compose.yml
    - frontend-admin-pro/package.json
    - frontend-admin-pro/package-lock.json
    - frontend-h5/package.json
    - frontend-h5/package-lock.json
    - lightmes-miniapp/package.json
---

## 1. 使用的系统与方法

仓库采用**多语言、多工作区**的依赖管理模式：
- Python 后端使用 `pip` + `requirements.txt` 声明式依赖，无虚拟环境或 Poetry/uv 等现代工具。
- 前端三个子项目（`frontend-admin-pro`、`frontend-h5`、`lightmes-miniapp`）均使用 `npm` + `package.json`，并通过 `package-lock.json` 锁定精确版本。
- 容器化构建通过 `backend/Dockerfile` 中的 `PIP_INDEX_URL` 构建参数切换 PyPI 源；前端镜像由 `docker/frontend/Dockerfile` 基于 Node 构建。
- 没有 vendored 第三方源码，也没有私有 PyPI/npm 仓库配置（如 `.pypirc`、`.npmrc`、`GOPRIVATE`），全部走公共源。

## 2. 关键文件与包

| 领域 | 关键文件 | 作用 |
|---|---|---|
| Python 运行时依赖 | `backend/requirements.txt` | FastAPI、SQLAlchemy、Alembic、Pydantic v2、Celery+Redis、OpenAI、ORM Tools、ChromaDB、Prophet、scikit-learn、pandas、numpy 等 |
| Python 可选依赖 | `backend/requirements-pdf.txt` | xhtml2pdf（HTML→PDF 打印模板，需先安装系统库 `libcairo2-dev`） |
| Python 容器构建 | `backend/Dockerfile` | 基于 `python:3.11-slim`，通过 `--build-arg PIP_INDEX_URL` 支持清华源替换 |
| 编排 | `docker-compose.yml` | 定义 mysql、redis、backend、web-admin、web-h5 五个服务 |
| 管理端前端 | `frontend-admin-pro/package.json` + `package-lock.json` | Vue 3 + Element Plus + Vite + TypeScript |
| H5 前端 | `frontend-h5/package.json` + `package-lock.json` | Vue 3 + Vant + Tailwind + Vite |
| 小程序前端 | `lightmes-miniapp/package.json` | uni-app 3.0 + Vue 3，含 `overrides` 强制 `path-to-regexp` 与 `jpeg-js` 版本 |

## 3. 架构与约定

### Python 依赖策略
- 所有运行时依赖集中在 `backend/requirements.txt`，测试依赖 `pytest` 也混在同一文件中。
- 对可能破坏 API 的大版本使用**上限约束**（upper bound）：`chromadb>=0.4.0,<1.0.0`、`prophet>=1.1.0,<2.0.0`、`scikit-learn>=1.3.0,<2.0.0`、`joblib>=1.3.0,<2.0.0`、`pandas>=2.0.0,<3.0.0`、`numpy>=1.24.0,<2.0.0`。这表明这些包在跨大版本时存在兼容风险，需要显式封顶。
- 核心框架仅使用 `>=` 宽松下限（如 `fastapi>=0.110.0`、`pydantic>=2.6.0`、`celery[redis]>=5.3.6`），不锁定具体小版本。
- PDF 渲染为**可选依赖**，单独放在 `requirements-pdf.txt`，Dockerfile 中不安装，需手动 `pip install -r requirements-pdf.txt`。
- Docker 构建默认使用官方 PyPI 源，但通过注释和 `ARG PIP_INDEX_URL` 明确支持国内镜像：`--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`。

### 前端依赖策略
- 每个前端子目录独立维护 `package.json`，三者共享部分生态（Vue 3、Pinia、Tailwind、Vite、TypeScript、ESLint），但 UI 组件库不同：管理端用 `element-plus`，H5 用 `vant`，小程序用 `@dcloudio/*` uni-app 全家桶。
- 所有前端都提交 `package-lock.json`（lockfileVersion 3），确保 CI/本地复现一致。
- 小程序 `lightmes-miniapp/package.json` 使用 `overrides` 字段强制覆盖传递依赖 `path-to-regexp` 到 `0.1.13`、`jpeg-js` 到 `0.4.4`，用于解决 uni-app 生态链中的安全/兼容问题。

### 容器与部署集成
- `docker-compose.yml` 将后端、MySQL 8.0、Redis 7-alpine、两个 Nginx 反代的前端打包为一个一键部署单元。
- 后端镜像通过 `backend/Dockerfile` 安装系统依赖 `libgomp1`（供 numpy/scipy/chromadb 的 OpenMP 使用），并设置 `PIP_NO_CACHE_DIR=1`、`PIP_DISABLE_PIP_VERSION_CHECK=1` 以加速构建。
- 前端镜像统一复用 `docker/frontend/Dockerfile`，通过 `FRONTEND` 构建参数区分 admin/h5 两个应用。

## 4. 观察到的约定与规则

- **Python 依赖集中声明**：除可选 PDF 模块外，所有 pip 依赖只出现在 `backend/requirements.txt`，没有在 `setup.py`、`pyproject.toml` 或其他位置重复声明。
- **大版本上限约束**：对 pandas、numpy、scikit-learn、prophet、chromadb、joblib 等数据科学类包显式添加 `<major` 上限，表明这些包跨大版本存在兼容性风险，升级时需人工验证。
- **可选依赖分离**：`requirements-pdf.txt` 作为可选依赖集，Dockerfile 中不自动安装，需用户按需执行 `apt install libcairo2-dev && pip install -r requirements-pdf.txt`。
- **PyPI 源可配置**：`backend/Dockerfile` 通过 `ARG PIP_INDEX_URL` 暴露 PyPI 镜像地址，默认 `https://pypi.org/simple`，注释指明国内部署应传清华源。
- **前端锁版本**：三个前端子项目均提交 `package-lock.json`，未使用 pnpm/yarn.lock，也未配置私有 registry。
- **uni-app 依赖覆盖**：`lightmes-miniapp/package.json` 使用 `overrides` 强制指定 `path-to-regexp` 与 `jpeg-js` 的精确版本，属于针对第三方漏洞/兼容性问题的补丁手段。
- **无私有仓库配置**：仓库中未发现 `.pypirc`、`.npmrc`、`PIP_TRUSTED_HOST`、`PYPI_MIRROR` 等私有源配置，所有第三方包均来自公共注册表。
- **无 vendoring**：没有 `vendor/`、`third_party/` 或内嵌的第三方源码，所有依赖均通过包管理器拉取。
