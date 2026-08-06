# 小程序 Mock 数据改真实 API

## 现状分析

### 已有真实 API 层（可直接复用）
- `src/api/http.ts` — 真实后端请求封装（`API_BASE = 'https://cenker.user.023ent.net/api'`，含 token/auth/错误处理）
- `src/api/h5.ts` — 员工端 H5 接口（已对接真实后端，含 dashboard/tasks/reports/salary/attendance/notifications）
- `src/api/crud.ts` — 通用 admin CRUD 封装（`crudList/crudGet/crudCreate/crudUpdate/crudRemove`）
- `src/api/auth.ts` — 认证接口（`loginWithPassword/fetchMe/miniappLogin/bindOpenid`）
- `src/api/files.ts` — 文件上传（`uploadFile/fileUrl`）
- `src/api/admin/entities.ts` — 管理端实体 CRUD（`entityList/entityGet/entityCreate/entityUpdate/entityRemove/EP` 端点常量/`approveLeader/approveQc/rejectReport`）

### 仍使用 Mock 的页面（共 14 个文件）

**客户自助端（7 个页面，全部 mock）：**
| 页面 | Mock 数据 | 后端 API |
|---|---|---|
| `pages-customer/home` | `mock.orders` | `GET /h5/customer/orders` |
| `pages-customer/order` | `mock.products` | `GET /h5/customer/catalog` |
| `pages-customer/order-form` | `mock.products` | `POST /h5/customer/orders` |
| `pages-customer/order-detail` | `mock.orders` | `GET /h5/customer/orders/{id}` + `/progress` |
| `pages-customer/progress` | `mock.orders` | `GET /h5/customer/orders` |
| `pages-customer/statement` | `mock.statements` | `GET /h5/customer/statements` + `POST /.../ack` |
| `pages-customer/invoice` | `mock.invoices` | 后端无发票 API |

**管理端（7 个页面/组件，全部 mock）：**
| 页面 | Mock 数据 | 后端 API |
|---|---|---|
| `pages-admin/dashboard` | `mock.dashboard` | `GET /dashboard/summary` + `GET /dashboard/charts` |
| `pages-admin/alerts` | `mock.alerts` | `GET /admin/ai/alerts` |
| `pages-admin/alert-detail` | `mock.alerts` | `GET /admin/ai/alerts` |
| `pages-admin/workorders` | `mock.workorders` | `GET /admin/production/work-orders` |
| `pages-admin/workorder-detail` | `mock.workorders` | `GET /admin/production/work-orders/{id}` |
| `pages-admin/audit` | `mock.auditList` | `GET /admin/production/reports?pending_audit=true` |
| `pages-admin/group` | 全部 mock | 各模块对应 endpoint（通过 `registry.ts` 的 `MODULE_MAP`） |

## 实施计划

### Step 1: 创建客户 API 层 `src/api/customer.ts`

新建文件，封装所有 `/h5/customer/*` 接口：

```typescript
import { apiGet, apiPost } from './http'

// 产品目录（客户可下单的产品/型号）
export function getCustomerCatalog(params?: { product_id?: number; keyword?: string }) {
  return apiGet<{ items: Sku[]; products: Product[] }>('/h5/customer/catalog', params as Record<string, unknown>)
}

// 我的订单列表
export function getMyOrders() {
  return apiGet<{ items: OrderItem[] }>('/h5/customer/orders')
}

// 订单详情
export function getOrderDetail(orderId: number) {
  return apiGet<OrderDetail>('/h5/customer/orders/' + orderId)
}

// 订单进度节点
export function getOrderProgress(orderId: number) {
  return apiGet<any>('/h5/customer/orders/' + orderId + '/progress')
}

// 自助下单
export function placeOrder(data: { items: { sku_id: number; qty: number; remark?: string }[]; remark?: string; due_date?: string; submit?: boolean }) {
  return apiPost<{ id: number; code: string; status: string }>('/h5/customer/orders', data)
}

// 对账单列表
export function getMyStatements(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: StatementItem[] }>('/h5/customer/statements', params as Record<string, unknown>)
}

// 对账单详情
export function getStatementDetail(statementId: number) {
  return apiGet<any>('/h5/customer/statements/' + statementId)
}

// 确认对账
export function ackStatement(statementId: number) {
  return apiPost<{ id: number; status: string }>('/h5/customer/statements/' + statementId + '/ack')
}

// 下载对账单 CSV URL
export function statementDownloadUrl(statementId: number): string {
  return API_BASE + '/h5/customer/statements/' + statementId + '/download'
}
```

### Step 2: 改造客户页面（7 个）

**`pages-customer/home/index.vue`**
- 移除 `import mock from '@/mock/index'`
- `onShow` 时调用 `getMyOrders()` 获取最近订单
- 调用 `fetchMe()` 获取客户名称（替换硬编码"宁波精工"）
- 订单状态映射：`pending_confirm`→待确认, `confirmed`→已确认, `in_production`→生产中, `completed`→已完成
- 数据字段映射：后端返回 `{ id, code, status, due_date, remark, created_at }`，前端需要 `product` 信息需从 `getOrderDetail` 或 `getOrderProgress` 获取（或简化显示 code + status + due_date）

**`pages-customer/order/index.vue`**
- 移除 `import mock`
- `onShow` 调用 `getCustomerCatalog()` 获取产品/型号列表
- 后端返回 `{ items: Sku[], products: Product[] }`
- 展示产品分组 + 型号列表（每个产品下挂其 SKU）
- 点击型号 → 跳到 `order-form?sku_id=xxx`

**`pages-customer/order-form/index.vue`**
- 移除 `import mock`
- `onLoad` 获取 `sku_id` 参数，调用 `getCustomerCatalog()` 获取产品选项
- 提交调用 `placeOrder({ items: [{ sku_id, qty }], due_date, submit: true })`
- 成功后跳转到 `progress` 页面

**`pages-customer/order-detail/index.vue`**
- 移除 `import mock`
- `onLoad` 获取 `id` 参数，调用 `getOrderDetail(id)` 获取订单信息
- 调用 `getOrderProgress(id)` 获取进度节点（后端返回 tasks 列表）
- 进度节点动态渲染：根据后端返回的 work_orders → tasks 构建时间线

**`pages-customer/progress/index.vue`**
- 移除 `import mock`
- `onShow` 调用 `getMyOrders()` 获取订单列表
- 进度百分比从 `order.progress` 字段获取（后端 `getOrderDetail` 返回 `progress` 字段）
- 搜索过滤在前端做（`kw` 过滤 code/product）

**`pages-customer/statement/index.vue`**
- 移除 `import mock`
- `onShow` 调用 `getMyStatements()` 获取对账单
- 确认对账调用 `ackStatement(id)`
- 金额从 `total_amount` 字段获取（后端返回数字，前端格式化）
- 下载对账单：`window.open(statementDownloadUrl(id))` 或 `uni.downloadFile`

**`pages-customer/invoice/index.vue`**
- 后端无发票 API
- 方案：保留 mock 数据，加注释标注"待后端发票模块上线后对接"
- 不改动此页面

### Step 3: 改造管理端页面（7 个）

**`pages-admin/dashboard/index.vue`**
- 后端有 `GET /dashboard/summary`（需 `dashboard.view` 权限）和 `GET /dashboard/charts`
- 但小程序端用户可能没有 `dashboard.view` 权限
- 方案：尝试调用 `GET /dashboard/summary`，失败则显示空状态 + 提示"无权限"
- 看板数据结构需适配：后端返回的是 `{ today_production, yield_rate, ... }`，与 mock 的 `{ stats, lines, recent }` 不同
- 简化方案：用 `GET /h5/dashboard/summary`（员工端接口，权限要求低）展示基础数据

**`pages-admin/alerts/index.vue`**
- 后端有 `GET /admin/ai/alerts`（需 `ai.alert.view` 权限）
- 返回 `{ items: [...] }`，每个 alert 有 `level/title/source/time/status` 等字段
- 与 mock 数据结构接近，可直接映射
- 失败则显示空状态

**`pages-admin/alert-detail/index.vue`**
- 从 `GET /admin/ai/alerts` 列表中找到对应 alert
- 或调用单独的详情接口（后端无单独详情 API，需从列表过滤）
- 方案：页面加载时调用 `GET /admin/ai/alerts`，按 id 过滤

**`pages-admin/workorders/index.vue`**
- 调用 `entityList(EP.workOrders, params)` 获取工单列表
- `EP.workOrders = '/admin/production/work-orders'`
- 后端返回 `{ items: [...] }` 或数组
- 状态筛选：全部/进行中/待派工/待排产/已完成 → 映射到后端 status 字段
- 后端工单 status 可能是 `pending/assigned/working/done` 等，需做中文映射

**`pages-admin/workorder-detail/index.vue`**
- 调用 `entityGet(EP.workOrders, id)` 获取工单详情
- 后端返回工单对象（含 `code, status, qty, progress, due_date, owner` 等）
- 派工/完成按钮：暂时保留 toast 提示（后端有派工 API 但较复杂）

**`pages-admin/audit/index.vue`**
- 调用 `entityList(EP.reports, { pending_audit: true })` 获取待审核报工
- 批量通过：循环调用 `approveLeader(id)`
- 后端 Report 模型有 `task/report_user/good_qty/bad_qty/status/attachment_ids` 字段

**`pages-admin/group/index.vue`**
- 这是管理端模块分组浏览页，当前全部用 mock
- 改造方案：每个分组调用对应的 `entityList(endpoint)` 获取真实数据
- `master` 分组：4 个 seg（产品/工序/员工/产线）→ 分别调用 `/admin/master/products`、`/admin/master/processes`、`/admin/system/users`、`/admin/master/lines`
- `production` 分组：调用 `/admin/production/work-orders`
- `equipment` 分组：调用 `/admin/equipment`
- `crm` 分组：调用 `/admin/production/customers`
- `finance` 分组：调用 `/admin/finance`（对账单）
- `notification` 分组：调用 `/admin/ai/alerts`
- `ai` 分组：暂无对应 API，保留 mock

### Step 4: 清理与验证

- 确认所有页面不再 `import mock`（invoice 除外）
- `mock/index.ts` 保留但标注"仅 invoice 页面开发调试用"
- 编译验证：`npx uni build -p mp-weixin`
- 检查 TypeScript 类型错误

## 依赖与假设

1. 后端 API 地址：`https://cenker.user.023ent.net/api`（已在 `http.ts` 配置）
2. 用户已登录且有对应角色（customer/admin），token 已存储在本地
3. 后端客户 API 需要用户有 `customer` 角色，管理 API 需要 `admin` 角色
4. 发票模块后端暂未实现，invoice 页面保留 mock
5. 管理端 dashboard/alerts 需要特定权限（`dashboard.view`/`ai.alert.view`），无权限时显示空状态

## 验证步骤

1. 编译通过：`npx uni build -p mp-weixin` 无错误
2. 客户端：登录后能看到真实订单/产品/对账单
3. 管理端：工单列表和报工审核显示真实数据
4. 看板/告警：如后端无权限，显示空状态
