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
