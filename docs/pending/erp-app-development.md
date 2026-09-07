# ERP App · 完整开发计划

> **App**：ERP 管理系统（key=`erp`）
> **机制**：基于 cenkor-admin 应用中心，manifest.py 声明式注册
> **部署路径**：本地内置（路径 A）+ ZIP 商店发布（路径 B），两者都要
> **基础位置**：`/www/wwwroot/cenkor-admin/backend/src/cenkor_admin/apps/erp/`
> **详细开发文档**：`apps/erp/docs/DEVELOPMENT.md`

---

## 一、目标

打造一个**真正可插拔**的 ERP 业务 App：
- ✅ 在 cenkor-admin 应用中心可见、可装、可卸
- ✅ 安装后自动建表 + 加权限 + 加菜单
- ✅ 后端路由自动注册到 `/api/v1/erp/*`
- ✅ 前端通过 `window.__registerPlugin()` 动态注入到 admin-web
- ✅ 可通过 dev.cenkor.cn 上传 + 审核 + 自动安装到任何部署实例

---

## 二、技术栈

| 层 | 技术 | 来源 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 | 沿用 cenkor-admin |
| 数据库 | PostgreSQL 16（默认）/ MySQL 5.7+（兼容）| 沿用 cenkor-admin |
| 前端 | Vue 3 + Vite library mode + Element Plus | 沿用 admin-web |
| 部署 | Docker Compose（cenkor-admin）/ ZIP | 双路径 |

---

## 三、模块设计（26 张表 + 39 个 API）

### Phase 2：客户管理（6 表 + 5 API）

**表**：
- `erp_customers` 客户主数据
- `erp_customer_contacts` 联系人
- `erp_customer_addresses` 多地址
- `erp_follow_ups` 跟进记录
- `erp_attachments` 附件
- （Phase 2 视情况加 `erp_customer_tags`）

**API**：
- `GET /api/v1/erp/customers`
- `GET /api/v1/erp/customers/{id}`
- `POST /api/v1/erp/customers`
- `PUT /api/v1/erp/customers/{id}`
- `DELETE /api/v1/erp/customers/{id}`

### Phase 3：供应商 + 商品（4 表 + 10 API）

**表**：
- `erp_suppliers` 供应商主数据
- `erp_supplier_contacts` 供应商联系人
- `erp_products` 商品主数据
- `erp_product_categories` 商品分类

**API**：5 供应商 + 5 商品

### Phase 4：销售订单（5 表 + 8 API）

**表**：
- `erp_quotations` 报价单
- `erp_quotation_items` 报价明细
- `erp_sales_orders` 销售订单
- `erp_sales_order_items` 订单明细
- `erp_shipments` 出货单

**API**：8 个（CRUD + 转报价 + 转订单 + 转出货）

### Phase 5：采购 + 仓库（6 表 + 8 API）

**表**：
- `erp_purchase_orders` 采购订单
- `erp_purchase_order_items` 采购明细
- `erp_purchase_receipts` 收货单
- `erp_warehouses` 仓库
- `erp_stock_balance` 库存余额
- `erp_stock_movements` 出入库流水

**API**：8 个

### Phase 6：财务（5 表 + 8 API）

**表**：
- `erp_invoices` 销售发票
- `erp_purchase_invoices` 采购发票
- `erp_payments` 收款记录
- `erp_accounts_receivable` 应收账款
- `erp_accounts_payable` 应付账款

**API**：8 个

### Phase 7：前端（9 页面 + 3 组件）

**页面**（Vite library mode 独立工程）：
- `CustomerListView.vue` 客户列表
- `CustomerEditView.vue` 客户详情
- `SupplierListView.vue` 供应商列表
- `ProductListView.vue` 商品列表
- `SalesOrderListView.vue` 销售订单列表
- `SalesOrderEditView.vue` 销售订单详情
- `PurchaseOrderListView.vue` 采购订单列表
- `WarehouseListView.vue` 仓库列表
- `FinanceView.vue` 财务总览

**组件**：
- `DataTable.vue` 通用表格
- `SearchBar.vue` 通用搜索栏
- `FormDrawer.vue` 通用表单抽屉

### Phase 8：打包发布（半天）

- `scripts/build.sh` 已就绪
- dev.cenkor.cn 提交
- 后台审核 + 安装

---

## 四、Phase 进度

| Phase | 任务 | 状态 |
|---|---|---|
| **Phase 1** | 脚手架 + alembic init + 脚本 + 文档 | ✅ 已完成 |
| Phase 2 | 客户管理 | 🔜 待开始 |
| Phase 3 | 供应商 + 商品 | ⏸ 等待 |
| Phase 4 | 销售订单 | ⏸ 等待 |
| Phase 5 | 采购 + 仓库 | ⏸ 等待 |
| Phase 6 | 财务 | ⏸ 等待 |
| Phase 7 | 前端 | ⏸ 等待 |
| Phase 8 | ZIP 打包发布 | ⏸ 等待 |

---

## 五、关键技术点

### 5.1 后端路由注册（无需改 api/v1/__init__.py）

`apps/erp/router/customer.py` 内的 `APIRouter` 在被 import 时即被纳入安装流程。具体由 `apps/system/app_registry.py` 处理：

```python
# app_registry.install_app 内会扫描 apps.erp.router.* 模块
# 自动 include_router 到 /api/v1/erp/*
```

### 5.2 前端运行时注册

`apps/erp/frontend/src/main.js`：

```js
window.__registerPlugin({
  id: 'erp',
  routes: [...],   // 9 个页面路由
  menus: [...],    // 7 个菜单
  locales: {...},  // i18n
})
```

`apps/erp/frontend/vite.config.js` 关键配置：

```js
build: {
  lib: {
    entry: './src/main.js',
    name: 'ErpPlugin',
    formats: ['iife'],
    fileName: () => 'plugin.js',
  },
  rollupOptions: {
    external: ['vue'],
    output: {
      globals: { vue: 'Vue' },
      inlineDynamicImports: true,
    },
  },
}
```

### 5.3 数据库迁移

`alembic/versions/20260831_0001_erp_init.py`（Phase 1 已就绪）

- `revision = "20260831_0001_erp_init"`
- `branch_labels = ("erp_app",)` —— 让应用中心知道这是哪个 App 的迁移
- `down_revision = None` —— 由安装流程根据已装 App 串接

后续 Phase 迁移文件命名：`20260831_NNNN_erp_<module>.py`

---

## 六、部署路径

### 路径 A：内置（开发用）

```bash
bash scripts/install.sh symlink
docker compose restart backend
# 应用中心 → 看到 erp → 点安装
```

### 路径 B：ZIP 商店发布

```bash
bash scripts/build.sh 1.0.0
# release/erp-1.0.0.zip
# 上传 dev.cenkor.cn → 审核 → 安装
```

---

## 七、风险与缓解

| 风险 | 缓解 |
|---|---|
| 路由路径冲突（cenkor-admin 已用 /api/v1）| 用 /api/v1/erp/* 命名空间隔离 |
| 权限点冲突 | erp: 前缀全部 |
| 表名冲突 | erp_ 前缀全部 |
| alembic 迁移链冲突 | 用 branch_labels="erp_app" 隔离分支 |
| 前端 plugin.js Vue 实例冲突 | vue external 共享 window.Vue |
| token 过期 | 用 window.__PLUGIN_API__ 自动 401 刷新 |

---

## 八、产出物

### 已完成（Phase 1）
- ✅ `apps/erp/__init__.py`
- ✅ `apps/erp/manifest.py`（20 权限 + 7 菜单）
- ✅ `apps/erp/alembic/versions/20260831_0001_erp_init.py`（6 表）
- ✅ `apps/erp/scripts/{build,install,dev}.sh`
- ✅ `apps/erp/docs/DEVELOPMENT.md`

### 待产出（Phase 2-8）
- ⏳ models/ schemas/ crud/ router/（Phase 2-6）
- ⏳ frontend/src/**（Phase 7）
- ⏳ release/erp-1.0.0.zip（Phase 8）
- ⏳ 9 个前端页面（Phase 7）

---

## 九、估算总工作量

| Phase | 估时 |
|---|---|
| Phase 1 | 4 小时（✅） |
| Phase 2 | 1.5 天 |
| Phase 3 | 1 天 |
| Phase 4 | 1.5 天 |
| Phase 5 | 1.5 天 |
| Phase 6 | 1.5 天 |
| Phase 7 | 2.5 天 |
| Phase 8 | 0.5 天 |
| **合计** | **~10 个工作日**（1-2 周单人） |

---

## 十、变更记录

| 日期 | 版本 | 变更 | 作者 |
|---|---|---|---|
| 2026-08-31 | v0.1 | 初稿 + Phase 1 完成 | AI 助理 |