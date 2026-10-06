# cenkormes 业务闭环审计与整改报告

日期：2026-10-05 ｜ 范围：`/www/wwwroot/cenkormes`（`ck.mes.cenkor.cn` 管理端 + `:8500` FastAPI）
口径：不看单点功能好不好用，看**一条业务数据从产生到能被对账、被追溯、被结算**这条路断在哪。
不含：`h5.mes.cenkor.cn`（那是另一套多租户项目，cenkormes 的 `frontend-h5` 未挂载）。

---

## 1. 结论摘要

| 类别 | 处置 | 验证 |
| --- | --- | --- |
| P0 单点崩溃（6 处） | 已修 | 后端用例通过 |
| 状态/金额写点不一致 | 已修 | 同上 |
| 账实一致（出货仓、外协出入库） | 已修（迁移 0008） | 同上 |
| 应收/应付口径分裂 | 已修（迁移 0007） | 同上 |
| 工资从未进总账 | 已修（迁移 0009） | 同上 |
| 审批/状态变更无留痕 | 已修（迁移 0010，新增 `approval_records`） | 11 条用例 |
| MRP 只看库存、算完不落采购单 | 已修（迁移 0011） | 12 条用例 |
| 飞书「送达诊断 / 规则模拟」有接口无界面 | 已补 UI | 类型检查通过 |
| 前端死 API 包装、幻影路由 | 已删（19 个方法 + 1 个整文件） | `vue-tsc -b` exit=0 |
| 权限粒度、Alembic 漂移、演示脚本脱节等 | **遗留**，见 §3 | — |

当前测试规模：**后端 272 passed**（`backend/tests/`，隔离 SQLite 内存库），前端 `vue-tsc -b` 无错误。
本报告写作时 **未构建 dist、未重启任何 Python 进程、未对开发 MySQL 执行写操作**（§4 有那次误操作记录）。

---

## 2. 已整改的问题（按批次）

### 第一批：P0 单点止血
六处直接报错或静默丢数据的单点问题（模型关系未注册导致 `loader` 报错、demo 数据脚本传了 schema 里不存在的 `tenant_id` 等）。特点是「一调用就炸」，不涉及口径。

### 第二批：状态与金额写点
同一状态/同一金额在多处各自赋值，改一处忘另一处。收敛到唯一的 crud 写点，API 层不再直接写 `status`/`amount`。

### 第三批：账实一致（`0008_stock_attribution`）
- 发货不记仓库：`shipments` 此前靠运行时「猜最低 ID 的启用仓」扣库存，单据上看不到扣了哪个仓 → 增加 `shipments.warehouse_id`。
- 外协发出/收回不入流水：`subcontract_send_logs` / `subcontract_receive_logs` 增加 `warehouse_id`，开始记库存变动。
- **原则**：新增列可空、历史行不回填。老单据读到空值表示「当时没记」，不伪造数据。

### 第四批：结构性缺口（4 项）

**4-1 应收口径统一（`0007_ar_ap_settlement`）**
问题：对账单状态是 `paid` 还是没付，账上没有唯一真相；`FinanceLedger` 里应计与现金两种口径混在一张表，回款率、账龄都算不出可信值。
处置：新增 `statement_payments` 逐笔核销流水（多态区分应收/应付），**现金唯一真相 = `StatementPayment`**；`FinanceLedger` 明确分应计（`ar`/`ap`）与现金（`receipt`/`payment`）；利润按应计口径，回款率读核销流水；支持部分核销与 `due_date` 账龄。

**4-2 工资落账与归属（`0009_salary_payment`）**
问题：`SalarySlip` 只有「员工签收」（`confirm_status`），**没有「厂里付了没有」这一层，所以工资从来没进过总账**，人工成本在现金流上是缺位的。
处置：新增发放四列（`pay_status`/`paid_at`/`paid_by`/`pay_method`），签收与付款是两条独立的线，互不推断；发放时写 `FinanceLedger(direction=out, category=labor, party_type=employee, statement_type=salary_slip)`。历史行一律 `unpaid`——没记过发放就是没记过。

**4-3 审批留痕（`0010_approval_records`）**
问题：订单驳回、采购作废、对账核销、工资条撤销这些「人做的决定」只写在 `confirmed_by/confirmed_at` 这类列上，改一次覆盖一次，**驳回历史无痕**，出了问题查不到是谁在什么状态下改的。
处置：新增**只追加**通用表 `approval_records`（`biz_type/biz_id` + 单号快照 + `action` + `from_status/to_status` + 操作人 id 与姓名快照 + `channel`(web/h5/system) + `reason` + JSON `detail`）。
- ORM 层 `before_update` / `before_delete` 事件监听直接抛 `RuntimeError`，改不动也删不掉。
- 覆盖 7 类单据：`order`、`purchase_order`、`warehouse_entry`、`statement`、`supplier_statement`、`salary_slip`、`mrp_plan`。
- 冲销不抹历史：`reverse` 行与原 `pay` 行并存在留痕里。
- 留痕时间可对齐单据自身时间戳（`slip.signed_at` / `paid_at`），保证回放顺序真实。
- 报工保留自己已有的 `ReportAudit`/`ReportUnitAudit`，**不重复记账**。
- 查询接口 `GET /admin/approval/records`（注意：必须注册在 `/admin/approval/{flow_id}` 之前，否则 `records` 会被当 flow_id 解析），管理端「系统 → 审批流」新增**审批留痕**页签。
- 原有出口一个没砍：h5 客户确认、h5 客户声明已付款（新增 `claim` 留痕）、采购作废（新增可选 `reason`）。

**4-4 MRP 落地（`0011_mrp_landing`，保留待完善）**
问题：净需求只减库存、**不减在途**，同一批料会被下一轮 MRP 反复建议再买；库存把停用仓也算进去；多张工单共用一种料时各自看一次全额库存（两张各需 60、库存 100，会说两头都不缺料）；算完只停在页面上，没有任何落地通道。
处置：净需求 = 毛需求 −（可用库存 + 在途未收量）；库存只算启用仓或指定的 `warehouse_ids`；同物料按行顺序扣**一个池**；`_last_purchase_hint` 回填最近单价与供应商（档案没填供应商时兜底，否则该行永远转不出去）；新增 `POST /admin/mrp/{plan_id}/convert` 按供应商分单、同物料合行，落 **draft 采购草稿单**（确认仍由人在采购页点），回写 `MrpItem.purchase_order_id`，计划状态 `converted`/`partial_converted`，并写 `mrp_plan` 留痕。
**仍待完善（有意保留）**：安全库存 / 最小起订量 / 批量裁剪、多阶 BOM 展开、供应商供货节奏对齐。

### 附带完成
- **飞书送达诊断 + 规则模拟 UI**：`POST /admin/system/feishu/simulate` 输出加厚（接收人带姓名、群带名称、逐条目标码命中情况 `by_code`、谁也没命中的 `unresolved`、规则是否停用 `enabled`）；管理端新增「送达诊断」「规则模拟」两个页签，人员绑定表每行加诊断入口；诊断展示抽成 `components/admin/FeishuDeliveryPanel.vue`；补齐三个语言包缺失的 `system.feishu.*` 键（其中 `p2pMessageCount` 是页面早就引用、语言包从来没定义，此前直接把键名渲染给了用户）。
- **前端死代码清理**：`api/production.ts` 行业包 5 个 + CRM 导入导出 6 个包装（后端 `app/api` 里连 `/admin/industry`、`.../crm/data-imports` 模块都不存在）；`api/purchase.ts` 对账单 8 个包装（真实路由是 `/admin/finance/supplier-statements*`，`/admin/purchase/statements*` 全是打不通的幻影）及随之失去用途的 4 个重复类型定义；`api/salary.ts` 整个文件零引用，删除（191 行）。

---

## 3. 遗留问题清单

### P1（会出错或能被越权，建议尽快处理）

1. **工资补贴写接口挂在「报工审核」权限下**
   `backend/app/api/admin/production/reports.py:27` 整块 router 要求 `report.audit`，而 `:306` 的 `POST /salary/allowances` 改的是钱。于是**质检员（qc 角色预设含 `report.audit`）、班组长都能给任意员工新增/修改工资补贴**，而这个动作本该要 `salary.manage`。
   建议：把 `salary/*` 三组接口拆到 `salary_reports.py` 并挂 `salary.manage`；`reports.py` 的只读列表另设 `report.view`。

2. **外协 router 没有任何权限依赖**
   `backend/app/api/admin/subcontract/router.py:23` 是裸 `APIRouter()`，仅靠挂载时的登录依赖保护 → 任何登录用户都能操作外协单。建议补 `require_permissions(["purchase.manage"])` 或独立的 `subcontract.manage`（后者需先在 `DEFAULT_PERMISSIONS` 里加）。

3. **看板 WebSocket 有连接、没有推送**
   `app/services/ws_hub.py` 的 `broadcast()` 实现了，但全项目只有 `app/api/ws/dashboard.py:45/57` 调用 `connect/disconnect`，**没有任何一处调用 broadcast** → 客户端连上后一直空等，实时看板实际靠轮询。要么接上生产者，要么把这条 WS 摘掉，别留半条路。

### P2（一致性/可用性，排期处理）

4. **`/admin/automation/dry-run`、`/admin/automation/logs` 前端完全没接**
   后端自动化排产有两个接口，`src/api/automation.ts` 只包了 `settings` 一个（还被 `PlansPage`/`PlanFormPage` 读取用）。排产自动化的试算与执行日志在管理端看不见，等于「自动化跑没跑、为什么这么排」无从核对。

5. **通知规则未注册事件静默返回 0**
   `app/services/notify_dispatcher.py:377` 对未注册事件 `return 0`。规则配了、事件名写错、页面显示成功、实际一条不发、日志零条——排错成本极高。建议：未知 `event_code` 直接 400，或落一条可见的失败记录（现在留痕/日志体系已经具备）。

6. **`stocks.qty >= 0` 只有应用层校验**
   数据库级 `CHECK` 约束未建（当时刻意搁置）。任何脚本、迁移补数、并发出库都可能把库存写成负数，而账实一致整批工作的前提就是这个数不为负。

### P3（噪音/技术债）

7. **20 个权限码「种子了但没人校验」**
   `app/core/seed.py` 共 57 个码，其中 20 个在 seed/rbac 之外没有任何代码引用：`report.submit`、`salary.view`、`warehouse.view`、`production.plan`、`workorder.view`、`workorder.manage`、`order.view/create/edit`、`task.view/assign`、`report.approve`、`qc.inspect/approve`、`customer.view`、`equipment.view`、`crm.admin`、`ai.use`、`ai.alert.view`、`erp.manage`。
   注意方向：`report.submit`、`salary.view` 等仍然被写进了角色预设 → **给了权限但没有代码校验它**，界面上一片勾，实际靠「登录即可」。要么补校验，要么从预设里摘掉，别给使用者虚假的安全感。

8. **`ai.use` / `ai.alert.view` / `erp.manage` 属于已下线模块**
   前端 ERP 分区与未挂载的 `api/` 目录本轮已移除，这三个码继续留着只会扩大 §3.7 的噪音。

---

## 4. 工程与部署风险（不是业务 bug，但会咬人）

- **Alembic 不是 schema 的唯一真相**。`0001_init_schema.py:27` 直接 `Base.metadata.create_all()`，导致 `approval_flows`/`approval_steps`/`finance_ledgers`/`salary_slips`/`report_units`/`mrp_*` 等表**只能靠启动时的 `create_all` 建立**，migration 链里没有它们的建表语句。后果：新环境只跑 `alembic upgrade head` 建不出完整库；反过来 migration 想 ALTER 这些表时必须先判存在（0009/0010/0011 都写了 `_table_exists` / `_column_exists` / 按列查外键的守卫，这是被迫的）。
- **`DB_AUTO_CREATE=true` 让「启动进程」变成 DDL 操作**。`.env` 打开该开关时 `app/main.py:97-99` 每次启动都 `create_all`。本轮就因此在开发库 `cenkermes` 上误建了 `approval_records`（已核对：列/索引正确、0 行、无数据损失）。教训：**任何**会加载 app 的动作（包括测试里用 TestClient）都可能改库，不是只有你手动重启才会。建议开发/测试环境默认关该开关，只在初次部署时开一次。
- **演示脚本已与 schema 脱节**。`backend/scripts/seed_demo_finance_data.py:72/76/80` 对 `orders`、`work_orders`、`finance_ledgers` 过滤 `tenant_id`，而这三张表都没有该列（cenkormes 核心表不带多租户字段）→ 一跑就 `Unknown column`。`demo_data_flow.py` 同源。要么改脚本，要么删掉，别留着误导人以为还有多租户隔离。
- **前端「构建即上线」**。nginx 根目录直指 `dist`，`npm run build` 成功的那一刻就是发布。本轮所有前端改动**只做了 `vue-tsc` 类型检查，没有构建、没有浏览器实机验证**（新页签需要登录态，我没有凭据也不该去动库）。

---

## 5. 本轮改动的生效步骤（按你的约定，进程由你自己启停）

1. 重启 `:8500` 后端进程（`app/crud/*`、`app/api/*` 全部改动都需要）。
2. `cd backend && .venv/bin/alembic upgrade head` —— 待应用：`0008`、`0009`、`0010`、`0011`（都带存在性守卫，与 `create_all` 已建的表不冲突）。
3. 需要上线前端时再构建 dist；构建即发布。
4. `api/salary.ts` 的删除目前处于 **git 暂存** 状态（用了 `git rm`），其余改动未暂存；本轮**没有 commit、没有 push**。

---

## 6. 建议的下一步（按性价比排序）

> 下面 8 条已全部落地：1/2/4/5/7/8 见 §7，3/6 见 §8。`DB_AUTO_CREATE` 保持开启（开发期）。

1. 拆 `reports.py` 的 `salary/*` 接口并挂 `salary.manage`（P1.1，越权改钱，改动小）。
2. 外协 router 补权限依赖（P1.2）。
3. 决策 WS 的去留：接上 broadcast 生产者，或整条摘掉（P1.3）。
4. 通知分发对未知事件报错而不是返回 0（P2.5），配合已有的留痕/日志把「配了没发」变成可见状态。
5. `stocks.qty >= 0` 的 DB 级 CHECK（P2.6）。
6. 把 `approval_flows/approval_steps/finance_ledgers/salary_*/report_units/mrp_*` 的建表补进 migration 链，让 `alembic upgrade` 单独能建出完整库（§4 第 1 条），之后关掉 `DB_AUTO_CREATE`。
7. 自动化排产 `dry-run`/`logs` 的前端入口（P2.4）——这是「自动化敢不敢用」的前提。
8. 权限码收敛：要么补校验、要么摘掉角色预设里的空转码（P3.7）。

---

## 7. 第二轮落地（2026-10-06，`pytest 309 passed` / `vue-tsc` 干净）

第 6 节 **1、2、4、5、7、8 已全部完成**，走的是「补校验」而不是「摘码」。3（WS 去留）和 6（建表补进 migration 链后关 `DB_AUTO_CREATE`）仍待决策/排期。

### P3.7 空转权限码 → 全部挂上真实校验

原则：**只做加法**。原来能用的授权通道一律保留，新码作为并列放行条件（`require_any_permissions`），因此没有任何现有角色会因为这次修复从 200 变 403；同时读/写职责真正分开——`.view` 码只解锁读，写仍需 `.manage`。

| 码 | 挂在哪 |
| --- | --- |
| `order.view` / `order.create` / `order.edit` | `production/orders.py` 逐路由：列表/详情/导出/打印走 view，`POST` 走 create，`PUT` 走 edit；删除、导入、`confirm`/`reject` 仍需 `order.manage` |
| `workorder.view` / `workorder.manage` | `work_orders.py`：5 条读接口 view 即可，批量打标 POST 需 manage |
| `task.view` / `task.assign` | `tasks.py`：任务列表/详情走 view，`PUT assignments`、`POST assign` 走 assign（`dispatch.manage` 仍是等价通道） |
| `production.plan` | `plans.py`：计划查询、排产看板、容量/日历走 production.plan；建/改/下发计划仍需 `plan.manage` |
| `equipment.view` | `equipment/router.py`：设备与维保的 5 个 GET 放开 view，7 个写接口逐条钉 `equipment.manage` |
| `warehouse.view` | `warehouse/router.py`+`material_issues.py`+`warehouse_entries.py`：库存、流水、领退料、入库单的 GET 放开 view；`stocks/adjust`、建单、确认、取消仍需 manage |
| `qc.inspect` / `qc.approve` / `report.approve` | `quality.py`（模板/缺陷码读=inspect，写=approve）、`report_units.py`（读=inspect，审批=approve/report.approve）、`reports.py`（`leader-approve` 认 report.approve，`qc-approve` 认 qc.approve） |
| `customer.view` | `production/customers.py` 读放开 view，建/改仍需 `customer.manage` |
| `crm.admin` | `/crm-adapter` 管理端与 `setting.manage` 并列 |
| `report.submit` / `salary.view` / `task.view` | H5 自助端：`POST /h5/reports`、`POST /h5/report-units` 认 report.submit；工资与工资单三条认 salary.view；任务/逐件读取认 task.view |

**顺带修掉一个被 §3.7 掩盖的真 bug**：H5 五个模块各自复制了一份 `_ensure_employee(user)`，判定写死 `{"employee","leader"}` 角色名 —— 开发库里 `worker`（7 个账号）、`workshop_leader`、`production_manager` 这些自建角色**在小程序/H5 上整片 403**，与权限点无关。现已改为按权限码判定（`app/api/h5/self_service.py`，一份判定四处复用），自建角色只要拿到 `task.view`/`report.submit`/`salary.view` 就能正常工作。

**没有校验对象的三个码保持原样**（如实说明，不假装修好）：`ai.use`、`ai.alert.view`、`erp.manage`。本仓 AI 只剩 `app/api/ai_compat/router.py` 三条返回固定空数据的占位路由（无 db、无 user、故意免登录以免 404），ERP 接口已整体移除 —— 没有可挂的读/写面。要它们真正管事，得先把功能做回来，或者按第 8 条建议从种子里摘除。

**H5 与仓储下拉保持「登录即可」，是有意的**：`/h5/attendance/*`（本人打卡）、`/h5/notifications/*`（本人消息）、`/h5/customer/*`（已按 `get_customer_by_user_id` 严格限定到当前账号自己，越权访问返回 403「仅客户账号可访问」）、`/admin/warehouse/options`（MRP、出入库页面都要用，`worker` 角色并不持有 warehouse.* 码）。给它们加权限只会把功能锁死，不解决任何越权。

**回归钉死**：`tests/test_permission_codes_live.py`（23 例）逐码验证「无码 403 → 有码 200 → view 码不能写」，并有一条防漂移用例：扫描 `app/` 全量源码，seed 里声明的每个码（除上表三个例外）必须出现在某个校验依赖里，否则测试失败。以后新增权限点忘了挂，CI 会直接红。

**前端同步**：`router/index.ts` 20 条 meta 与 `AppMenu.vue` 19 条菜单项补上对应的 `.view`/`.assign`/`.approve` 码，否则只读角色拿得到接口却进不了页面。**尚未做**：页面内写操作按钮的按码隐藏（本仓历来没有按钮级 `v-if` 权限约定，只读角色点开按钮会收到 403 提示）——需要的话按页面逐个补。

---

## 8. 第三轮落地（2026-10-06，`pytest 327 passed`）

### 8.1 §3 P1.3 —— 看板 WebSocket 从「只有消费者」变成有生产者

原先 `dashboard_ws_hub.broadcast` 零调用者，`/api/ws/dashboard` 每 15 秒给每个连接
硬发一条 `refresh`，等于把事件推送做成了轮询。现在：

- `app/services/dashboard_events.py`（新）：在 `Session` 类级事件上挂钩子
  ——`before_flush` 记下本事务改到了哪几张看板表，`after_commit` 才广播，`after_rollback` 丢弃。
  监听的是 `Report / ReportUnit / ReportUnitAudit / Order / OrderItem / WorkOrder / Task / TaskAssignment / SalaryItem`，
  对应 `changed: ["reports"|"orders"|"tasks"|"salary"]`。
  选这个挂点而不是逐个端点手写调用：这些表的写入点散在 admin、h5、自动化、脚本里，逐个补必漏。
- `app/services/ws_hub.py`：`publish()` 用 `run_coroutine_threadsafe` 把消息从同步线程
  （线程池里的端点）投回事件循环；`publish_refresh()` 带 3 秒合并窗口，窗口内的多次提交
  只推一次，并在窗口结束时补发一次，保证最后一笔改动一定被看到。推送失败只记日志，不影响已提交的业务事务。
- `app/api/ws/dashboard.py`：空闲窗口 15s → 45s，`refresh` 从「唯一来源」降级为漏推兜底。
- 前端不用改：`utils/ws.ts` 仍只认 `type === "refresh"`，nginx 的 `/api/ws/` 已配好
  `Upgrade`+`proxy_read_timeout 86400s`，`:8500` 单进程 → 进程内存连接池够用。多 worker 部署要换 Redis pub/sub。

证据：`tests/test_dashboard_ws_refresh.py`（11 例，含跨线程投递、合并窗口、僵尸 handle 重挂、死 socket 摘除）
+ `tests/test_dashboard_ws_live_push.py`（3 例，真接口 `POST /api/admin/production/orders`
commit 后，已连接的 WS 客户端真的收到 `{"type":"refresh","changed":["orders",...]}`）。

### 8.2 §4 第 6 条 —— 迁移链现在能单独建出完整库

跑之前先说结论：**在此之前它跑不通第二遍**。`0001_init_schema.upgrade()` 是
`Base.metadata.create_all(bind=app.core.db.engine)`，于是：

| 问题 | 后果 |
| --- | --- |
| 建表内容取决于 `app/models/__init__.py` 当时导入了哪些模块 | `molds/quotations/spc_*/wechat` 共 9 张表既没进迁移也没被建出来（老库和新库结构不一致） |
| 用的是 `settings.DB_URL` 的 engine，而不是 alembic 的 bind | `alembic -x` / `ALEMBIC_DB_URL` 指哪都没用，永远迁主库 |
| 0005/0007 无守卫地 `create_table` / `add_column` | 空库跑到 0005 直接 `table cloud_storage_config already exists` —— 链不可重放 |
| 0002/0003/0008–0012 的幂等守卫写死 `information_schema` | 只能在 MySQL 上跑，「能不能从零建库」无法在不碰真实库的前提下验证 |

改动：

1. `alembic/env.py`：新增 `ALEMBIC_DB_URL` 覆盖（未设置时回落 `settings.DB_URL`）；
   导入 `app/models` 下全部模块 + `crm_adapter` 模型，让 metadata 不再依赖导入副作用。
2. `0001`：改用 `op.get_bind()`；离线 `--sql` 模式给出明确报错（create_all 无法渲染成 SQL）。
3. `0005`、`0007`：逐条加 `has_table` / `has_column` / `has_index` 守卫，`drop_table(if_exists=True)`。
4. `0002/0003/0008/0009/0010/0011/0012`：7 个文件里的 15 个守卫函数从裸 `information_schema`
   换成 `sa.inspect(conn)`，语义不变但方言无关。
5. `0013_orphan_model_tables`（新）：按名字补齐上述 9 张表，DDL 取模型元数据（不复制第二份定义）。
   **已在开发库执行**：125 → 134 张表，`current = 0013_orphan_model_tables (head)`。
   回滚就是 `downgrade 0012`（已在 SQLite 上验证会干净地删掉这 9 张）。

验证（全程不碰 MySQL）：空库 `alembic upgrade head` → 126 张表，覆盖 125 个模型表，
之后再跑 `create_all` 增量为 0；链在 dev 式模拟库上单独补建出那 9 张；dev 与「空库跑链」
在 116 张共有表上**列级零漂移**。回归用例见 `tests/test_alembic_chain_complete.py`（4 例）。

`ai_alert_events / ai_conversations / ai_messages / platform_ai_* / wecom_push_logs / dingtalk_push_logs`
这 8 张表：模型已删、代码零引用、链也不建，只躺在老库里 —— 是历史遗留，不动它（不删别人的数据），
但加了用例守住「链不建的表不能有代码引用」。

**`DB_AUTO_CREATE` 现在可以关了**，但你在开发期关掉之后，新增模型必须自己配一条像 0013 那样的
迁移，否则老库不会长出这张表（新库反而会）—— 建议发布前再关。

### 8.3 §6 第 8 条相关 —— 演示数据脚本的租户列

`scripts/seed_demo_finance_data.py` 全文按 `tenant_id` 过滤/插入，而
`orders / work_orders / order_items / finance_ledgers` 四张表都没有这一列（已用开发库
`information_schema` 只读确认），脚本一进去就 `Unknown column`。已去掉租户过滤与
`tenant_id=` 入参，`_is_already_seeded` 改为全表判断。在隔离 SQLite 上干跑通过
（orders 7 / work_orders 6 / 台账 18 条，二次运行正确跳过）。**脚本会写库，仍由你自己决定何时跑。**

注：`_is_already_seeded` 现在只要 `finance_ledgers` 有任何一行就跳过 —— 开发库已有 1 行，
所以现在跑它会 `[SKIP]`。这是原本就有的保守语义，没有改。
