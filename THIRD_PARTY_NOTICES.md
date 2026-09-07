# THIRD-PARTY NOTICES

CenkorMES 基于众多开源库构建。下表列出本项目直接依赖的第三方开源组件及其许可证。

本项目本身采用 **GNU AGPL-3.0** 许可，详见根目录 [LICENSE](./LICENSE)。
下表列出的组件只要不与 AGPL-3.0 冲突，均保留其原始许可证条款。

如需对应许可证的完整法律文本，请通过各组件官方仓库或对应许可证组织查阅。

---

## 前端（frontend-admin-pro / frontend-h5 / lightmes-miniapp）

### 运行时依赖

| 组件 | 项目（模块） | 许可证 |
| --- | --- | --- |
| Vue | `vue` | MIT |
| Vue Router | `vue-router` | MIT |
| Pinia | `pinia` | MIT |
| Vue I18n | `vue-i18n` | MIT |
| axios | `axios` | MIT |
| lucide-vue-next | `lucide-vue-next` | ISC |
| clsx | `clsx` | MIT |
| tailwind-merge | `tailwind-merge` | MIT |
| tailwindcss | `tailwindcss` | MIT |
| Element Plus | `element-plus` | MIT |
| Element Plus Icons | `@element-plus/icons-vue` | MIT |
| Vant | `vant` | MIT |
| echarts | `echarts` | Apache-2.0 |
| vue-echarts | `vue-echarts` | MIT |
| @unhead/vue | `@unhead/vue` | MIT |
| @dcloudio/uni-app 系列 | `@dcloudio/uni-app`, `uni-app-plus`, `uni-components`, `uni-h5`, `uni-mp-weixin` | Apache-2.0 |

### 构建/开发依赖（主要）

| 组件 | 许可证 |
| --- | --- |
| TypeScript | Apache-2.0 |
| Vite | MIT |
| vue-tsc | MIT |
| ESLint | MIT |
| sass / postcss / autoprefixer | MIT |
| @vitejs/plugin-vue | MIT |
| @dcloudio/*（构建工具） | Apache-2.0 |

> 说明：`lightmes-miniapp` 依赖 `path-to-regexp`（MIT）与 `jpeg-js`（MIT），已通过 `overrides` 固定版本。

---

## 后端（backend）

### 主要依赖

| 组件 | 项目 | 许可证 |
| --- | --- | --- |
| FastAPI | `fastapi` | MIT |
| Uvicorn | `uvicorn` | BSD-3-Clause |
| SQLAlchemy | `sqlalchemy` | MIT |
| Alembic | `alembic` | MIT |
| Pydantic | `pydantic`, `pydantic-settings` | MIT |
| python-jose | `python-jose` | MIT |
| bcrypt | `bcrypt` | Apache-2.0 |
| PyMySQL | `pymysql` | MIT |
| python-multipart | `python-multipart` | MIT |
| aiofiles | `aiofiles` | Apache-2.0 |
| openpyxl | `openpyxl` | MIT |
| Celery | `celery` | BSD-3-Clause |
| qrcode | `qrcode` | MIT |
| httpx | `httpx` | BSD-3-Clause |
| Redis 客户端 | `redis` | MIT |
| Pillow | `pillow` | HPND（Historical Permission Notice） |
| pytest | `pytest` | MIT |

### 云存储 / 消息 SDK

| 组件 | 项目 | 许可证 |
| --- | --- | --- |
| Aliyun OSS SDK | `oss2` | MIT |
| Tencent COS SDK | `cos-python-sdk-v5` | MIT |
| 七牛 Kodo SDK | `qiniu` | MIT |

### AI / 数据处理（可选增强能力）

| 组件 | 项目 | 许可证 |
| --- | --- | --- |
| openai | `openai` | Apache-2.0 |
| OR-Tools | `ortools` | Apache-2.0 |
| chromadb | `chromadb` | Apache-2.0 |
| Prophet | `prophet` | MIT |
| scikit-learn | `scikit-learn` | BSD-3-Clause |
| joblib | `joblib` | BSD-3-Clause |
| pandas | `pandas` | BSD-3-Clause |
| numpy | `numpy` | BSD-3-Clause |

---

## 许可证兼容性说明

- 上表中的许可证（MIT / Apache-2.0 / BSD-3-Clause / ISC / HPND）均为**宽松许可证**，与 AGPL-3.0 **兼容**，可在同一发行版内共存。
- AGPL-3.0 的传染性要求仅针对**对 CenkorMES 源码本身的修改与再分发**（或对外提供网络服务时开源其运行实例源码），不影响以“动态链接/独立进程 + 各自许可证”方式使用的上述库。
- 若你在派生版本中改动了 CenkorMES 源码并对外提供服务或分发，需按 AGPL-3.0 提供对应源码；详见 [LICENSE](./LICENSE)。

---

*本文件由 CenkorMES Project 维护。所列版本以各仓库当前部署的 `package.json` / `requirements.txt` 为准，如有出入以官方许可证文本为准。*