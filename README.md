# CenkorMES — 轻量化生产管理系统

基于 CenkorMES 重构的单租户私有部署版 MES，聚焦中小型加工厂的核心生产管理闭环。

## 核心功能闭环

```
产品/型号 → 工序/工价 → 客户/订单 → 工单 → 派工/任务 → 扫码报工 → 审核 → 自动算薪
```

### 保留模块
- **基础数据**: 产品、SKU/型号、工序、工价、工艺路线、物料、BOM、供应商
- **生产管理**: 订单、工单、任务派工、报工审核、质检、工资核算、溯源
- **排产管理**: 生产计划、甘特图、产能检查
- **设备管理**: 设备档案、点检、保养计划
- **客户管理**: 客户档案、订单历史
- **系统设置**: 用户、角色、权限、部门、字典、日志
- **员工端 (H5)**: 扫码报工、任务查看、考勤打卡、工资查询
- **客户端 (H5)**: 自助下单、订单进度、对账单
- **微信小程序**: 员工报工(精简版)

## 与商业 SaaS 版（lightmes）的关系

本仓库是 **CenkorMES 独立版**（单租户私有部署，开源）。与之配套的商业 **SaaS 版（lightmes）** 采用多租户云端模式并商业收费，二者定位与功能边界如下：

| 维度 | 开源独立版（本仓库 / cenkormes） | 商业 SaaS 版（lightmes） |
|------|--------------------------------|--------------------------|
| 部署方式 | 单租户独立部署 | 多租户云 SaaS |
| 开源 / 许可 | ✅ 开源（AGPL-3.0） | 商业授权收费 |
| SaaS 平台层（租户 / 套餐 / 订阅订单） | ✕ | ✅ |
| AI 员工 | ✕ | ✅ |
| 行业模板 | ✕ | ✅ |
| 报价（quotation） | ✕ | ✅ |
| SPC 统计过程控制 | 仅表结构，功能未开放 | ✅ |
| 模具管理（mold） | 仅表结构，功能未开放 | ✅ |
| 文档打印模板 | ✅ | ✅ |
| 飞书 / 钉钉 / 企微消息通道 | ✅ | ✅ |
| 核心制造闭环（排产 / 工单 / 报工 / 质检 / 库存 / 采购 / 追溯 / 外协 / MRP） | ✅ | ✅ |
| 特色亮点 | trace 追溯树、crm-adapter、执行看板 | — |

> 开源独立版完整保留生产管理核心闭环，天然不含 SaaS 平台层与高级增值功能，商业增值能力集中在 SaaS 版。详细差异见 [`docs/cenkormes-vs-lightmes.html`](docs/cenkormes-vs-lightmes.html)。

---
## 鸣谢（Acknowledgements）

CenkorMES 深度构建在众多优秀的开源项目与第三方组件之上，本系统得以稳定运行、开发与交付，离不开这些上游项目的作者与广大社区长期无私的贡献。在此向以下技术与项目致以诚挚敬意：

**前端与小程序**

| 依赖 | 用途 | 官方主页 / 仓库 |
|------|------|-----------------|
| [Vue 3](https://github.com/vuejs/core) | 核心渐进式框架 | github.com/vuejs/core · MIT |
| [Vue Router](https://github.com/vuejs/router) | 前端路由 | github.com/vuejs/router · MIT |
| [Pinia](https://github.com/vuejs/pinia) | 状态管理 | github.com/vuejs/pinia · MIT |
| [vue-i18n](https://github.com/intlify/vue-i18n-next) | 国际化 | github.com/intlify/vue-i18n-next · MIT |
| [Element Plus](https://github.com/element-plus/element-plus) | 桌面端组件库 | github.com/element-plus/element-plus · MIT |
| [Vant 4](https://github.com/youzan/vant) | 移动端组件库 | github.com/youzan/vant · MIT |
| [Apache ECharts](https://github.com/apache/echarts) | 数据图表与看板 | github.com/apache/echarts · Apache-2.0 |
| [vue-echarts](https://github.com/ecomfe/vue-echarts) | Vue 中的 ECharts 封装 | github.com/ecomfe/vue-echarts · MIT |
| [bpmn-js](https://github.com/bpmn-io/bpmn-js) | 审批 / 工作流流程图设计器 | github.com/bpmn-io/bpmn-js · bpmn.io License |
| [Axios](https://github.com/axios/axios) | HTTP 请求 | github.com/axios/axios · MIT |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) | 原子化 CSS | github.com/tailwindlabs/tailwindcss · MIT |
| [lucide-vue-next](https://github.com/lucide-icons/lucide) | 图标 | github.com/lucide-icons/lucide · ISC |
| [uni-app](https://github.com/dcloudio/uni-app) | 跨端小程序框架 | github.com/dcloudio/uni-app · Apache-2.0 |
| 微信同声传译插件（WechatSI） | 语音识别报工 | 微信官方小程序插件平台 |

**后端与数据**

| 依赖 | 用途 | 官方主页 / 仓库 |
|------|------|-----------------|
| [FastAPI](https://github.com/fastapi/fastapi) | 异步 Web 框架 | github.com/fastapi/fastapi · MIT |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | ORM | github.com/sqlalchemy/sqlalchemy · MIT |
| [Pydantic](https://github.com/pydantic/pydantic) | 数据校验 | github.com/pydantic/pydantic · MIT |
| [alembic](https://github.com/sqlalchemy/alembic) | 数据库迁移 | github.com/sqlalchemy/alembic · MIT |
| [Celery](https://github.com/celery/celery) | 异步任务与定时调度 | github.com/celery/celery · BSD-3-Clause |
| [Redis](https://github.com/redis/redis) | 缓存 / 消息中间件 | github.com/redis/redis · BSD-3-Clause |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | 大模型调用 | github.com/openai/openai-python · Apache-2.0 |
| [ChromaDB](https://github.com/chroma-core/chroma) | RAG 向量数据库 | github.com/chroma-core/chroma · Apache-2.0 |
| [Google OR-Tools](https://github.com/google/or-tools) | 排产 / 运筹优化 | github.com/google/or-tools · Apache-2.0 |
| [Prophet](https://github.com/facebook/prophet) | 时间序列预测 | github.com/facebook/prophet · MIT |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | 机器学习 | github.com/scikit-learn/scikit-learn · BSD-3-Clause |
| [pandas](https://github.com/pandas-dev/pandas) | 数据分析 | github.com/pandas-dev/pandas · BSD-3-Clause |
| [numpy](https://github.com/numpy/numpy) | 数值计算 | github.com/numpy/numpy · BSD-3-Clause |
| [python-jose](https://github.com/mpdavis/python-jose) | JWT 签名 | github.com/mpdavis/python-jose · MIT |
| [bcrypt](https://github.com/pyca/bcrypt) | 密码哈希 | github.com/pyca/bcrypt · Apache-2.0 |
| [PyMySQL](https://github.com/PyMySQL/PyMySQL) | MySQL 驱动 | github.com/PyMySQL/PyMySQL · MIT |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | Excel 读写 | openpyxl · MIT |
| [httpx](https://github.com/encode/httpx) | HTTP 客户端 | github.com/encode/httpx · BSD-3-Clause |
| [Pillow](https://github.com/python-pillow/Pillow) | 图像处理 | github.com/python-pillow/Pillow · HPND |
| 阿里云 OSS SDK / 腾讯云 COS SDK / 七牛 Kodo SDK | 对象存储 | 各云厂商官方 SDK |
| [pytest](https://github.com/pytest-dev/pytest) | 单元测试 | github.com/pytest-dev/pytest · MIT |

我们严格遵循各上游开源许可证（MIT / Apache-2.0 / BSD-3-Clause / ISC / HPND / AGPL 兼容），并在分发时完整保留其版权与许可声明。

> 完整、逐条的第三方依赖许可证清单，请参阅 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) 与 [LICENSE](./LICENSE)。我们对每一位开源贡献者再次表示感谢。

## 快速启动

### 环境要求
- Python 3.10+
- Node.js 18+
- MySQL 5.7+
- Redis (可选，用于 Celery 异步任务)

### 1. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env  # 编辑数据库配置
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

首次启动自动创建数据库表和种子数据。

### 2. 启动管理后台 (PC)

```bash
cd frontend-admin-pro
npm install
npm run dev -- --port 5174
```

访问 http://localhost:5174

### 3. 启动 H5 移动端

```bash
cd frontend-h5
npm install
npm run dev -- --port 5173
```

访问 http://localhost:5173

### 4. Docker 一键启动

```bash
docker compose up -d
```

## 默认账号

首次启动系统自动创建管理员账号：
- 用户名: `admin`
- 密码: `admin123`

请及时修改密码。

## 项目结构

```
cenkormes/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── core/            # 核心配置
│   │   ├── models/          # ORM 模型
│   │   ├── schemas/         # Pydantic 校验
│   │   ├── crud/            # 数据访问层
│   │   ├── services/        # 业务逻辑层
│   │   └── tasks/           # Celery 异步任务
│   ├── alembic/             # 数据库迁移
│   └── requirements.txt
├── frontend-admin-pro/      # PC 管理后台 (Vue 3 + Element Plus)
├── frontend-h5/             # H5 移动端 (Vue 3 + Vant 4)
└── lightmes-miniapp/        # 微信小程序 (uni-app, 员工版)
```

## License

本项目采用 **AGPL-3.0** 开源许可证，详见 [LICENSE](./LICENSE)。

第三方依赖及其许可证声明见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。