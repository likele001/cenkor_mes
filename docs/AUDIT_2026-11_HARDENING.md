# CenkorMES 深度审计（2026-11）与加固计划

> 范围：`/www/wwwroot/cenkormes`（单实例版），后端 `backend/app`、管理端 `frontend-admin-pro`、H5 `frontend-h5`、运维脚本与 CI。
> 方法：四路并行静态审计（后端缺陷、前端缺陷、运维可靠性、业务闭环），关键结论均回读代码复核。
> 约束：不连生产库、不重启进程、不读 `.env`。第一批已落地（第 2.1 节），第二批及以后仅为方案。

## 一、结论摘要

订单 → 计划 → 工单 → 报工 → 工资/追溯主链可运行；问题集中在三处：

1. **权限收口不严**：公开/登录即可访问的回调与附件、审批留痕缺少业务权限。
2. **并发与账实**：对账单核销、采购收货、领料/入库过账缺少行锁或幂等，双击或并发会重复过账/超收。
3. **伪成功**：CRM 报价转订单只改状态不建单，用户误以为已转单。

另有销售/售后/质检/调拨等业务闭环缺口，见第四部分，作为后续批次。

## 二、第一批：安全与账实（本次实施）

| # | 问题 | 位置 | 修法 | 验证 |
|---|---|---|---|---|
| 1 | 报价转订单只改状态、`converted_order_id` 恒空 | `backend/app/crud/crm.py:1226`、`api/admin/production/crm.py:1050` | 校验状态/客户/明细，生成订单与明细并带入报价单价；已有订单时幂等返回 | 新增单测：转单成功、金额一致、重复转单不新建、缺 SKU/非法状态报错 |
| 2 | 核销读改写无行锁，并发可超收 | `backend/app/crud/statement_payment.py:122` | 读取对账单时 `SELECT ... FOR UPDATE`，锁内校验余额并累计 | 单测覆盖余额校验；MySQL 上验证并发（手工） |
| 3 | 附件下载仅要求登录 | `backend/app/api/v1/files.py:122` | 上传者本人、超级管理员或具 `attachment.view` 才可读；删除失败不再静默吞异常 | 单测：本人可读、无权限 403、有权限可读 |
| 4 | 审批留痕只校验登录，可读工资/对账明细 | `backend/app/api/admin/approval/records.py:53` | 按 `biz_type` 映射业务权限；不带类型时只返回有权类型的数据 | 单测：员工查工资留痕 403、管理员可查 |
| 5 | 飞书回调不验签，配置了 Encrypt Key 仍接受明文 | `backend/app/api/feishu/router.py:27`、`services/feishu/callbacks.py:36` | 配置 Encrypt Key 后强制加密报文；配置 Verification Token 后校验 token；失败 403 | 单测：明文被拒、token 不符被拒、正常加密/明文（未配置）通过 |
| 6 | 升级构建/迁移失败后代码停在新 tag，形成"新代码+旧库" | `backend/app/services/upgrade_service.py:369-560` | 构建/迁移/换入失败时 `git checkout -f from_ref` 并记录；dist 临时目录清理 | 单测：构建失败回滚代码、迁移失败回滚代码、成功不回滚 |
| 7 | `/api/health` 不探依赖，异常全包 200 | `backend/app/main.py:76` | health 执行 `SELECT 1`；数据库不可用返回 HTTP 503 + `status=degraded` | 单测：正常 200、DB 异常 503（monkeypatch） |
| 8 | 非 dev 环境仍会创建 `admin/admin123` | `backend/app/core/config.py:17`、`main.py:139` | 非 dev 仅在设置 `ADMIN_INIT_PASSWORD`（≥最小长度）时创建；否则告警跳过 | 单测：dev 默认、非 dev 无密码跳过、有密码创建 |
| 9 | 采购收货/领料/入库单并发重复过账 | `api/admin/purchase/orders.py:166`、`crud/material_issue.py:103`、`crud/warehouse_entry.py:159` | 事务内锁定单据行并二次校验状态，再改库存 | 单测：已过账单据再次提交报错；正常流程不变 |

### 2.1 实施记录

新增文件：

- `backend/app/crud/locking.py`：`lock_row` 行锁助手（按主键锁定并刷新）。
- `backend/tests/test_batch1_quote_convert.py`（7 例）
- `backend/tests/test_batch1_statement_payment.py`（6 例）
- `backend/tests/test_batch1_permissions.py`（12 例）
- `backend/tests/test_batch1_security_basics.py`（14 例）
- `backend/tests/test_batch1_stock_posting.py`（8 例）
- `backend/tests/test_upgrade_recovery.py`（8 例）

改动文件：

- 报价转单：`crud/crm.py`（真实建单，幂等，折扣折算单价，拒绝小数数量/缺 SKU）。
- 行锁与幂等：`crud/statement_payment.py`、`crud/material_issue.py`、`crud/warehouse_entry.py`、`api/admin/purchase/orders.py`。
- 权限：`api/v1/files.py`（附件读取）、`api/admin/approval/records.py` + `crud/approval_record.py`（按业务类型过滤）、`api/admin/system/attachments.py`（删除失败不再静默）。
- 角色预设：`core/seed.py` 给班组长/质检补 `attachment.view`，保证审核员工报工照片、工资条签名不被误挡；员工仍只能读自己上传的文件。
- 飞书：`services/feishu/callbacks.py`、`api/feishu/router.py`（强制加密 + token 校验，失败 403）。
- 升级：`services/upgrade_service.py`（失败时 `git checkout -f from_ref`、回退已换入的 dist、清理临时目录）。
- 启动与健康：`main.py`（`SELECT 1` 探测、`_ensure_default_admin`）、`core/config.py`（`ADMIN_INIT_PASSWORD`）。
- 既有用例适配：`tests/test_closedloop_p4_audit.py` 调用留痕接口时补传权限码。

验证结果（2026-11）：

- `pytest backend/tests -q`：**544 passed**（含新增 55 例）。
- 无数据库迁移；前端无改动，未重新构建。
- 变更留在工作区，未提交。

### 兼容性与边界

- 不改响应包络（业务错误仍以 HTTP 200 + `code` 返回），避免管理端/H5 大面积回归；仅 health 在依赖故障时返回 503。
- 行锁依赖 MySQL；SQLite 测试库会忽略 `FOR UPDATE`，并发语义需在 MySQL 上手工复核。
- 报价数量为小数时拒绝转单并提示（核心订单数量为整数），不做静默取整。
- 升级失败回滚只回代码，不回滚已执行的数据库迁移（MySQL DDL 不可事务回滚）；日志明确标注。

## 三、第二批：业务闭环（待排期）

| 能力 | 现状 | 量级 |
|---|---|---|
| 批量报工成品入库 | 仅逐件模式入库，批量终审不入库 | S |
| 发货校验订单余量与分批状态 | 可超发；首批发货即整单 shipped | M |
| 采购退货冲应付 | 对账只算 `received_qty`，不减退货 | S |
| 按发货对账、金额用订单售价 | 仅按订单、按工价口径 | M |
| 售后闭环：退货入库 + 冲应收 | 售后单只有状态 | M |
| 来料检验 + 不合格处置 | 收货直接入账，无 IQC | M |
| 调拨单 | 无模型，只能两笔调整 | M |
| 工单拆分/关闭/返工/报废 | 状态只能由报工推导 | M |
| 设备保养自动生成任务/提醒 | `next_date` 只在录日志时推进 | S/M |
| 库存预留/ATP，统一齐套与 MRP 口径 | 齐套不减在途 | L |
| 物料批次 → 成品追溯 | 仅逐件模式 | L |

## 四、第三批：前端与工程债

- 7 个列表只取 50 条且无分页控件（报工、领料、BOM、工资条、追溯等），第 51 条起不可见。
- H5 `/report-unit` 被顶层路由遮蔽，页面脱离布局；401 只弹提示不清登录态；考勤双击可重复打卡。
- 上传复用 15/20 秒全局超时，大视频必失败；H5 报工媒体未传 `purpose`。
- 升级/扩展运维：进程被 OOM 后任务永久 running 阻塞后续升级；扩展迁移先动库后换版；备份无保留/异地策略。
- CI 仅 SQLite 跑测试，未在 MySQL 上做 `alembic upgrade head` 冒烟。
- 死权限码 `erp.manage` 无消费方；部分扩展宿主 docstring 与实现不符。

## 五、暂不做

- 套餐分层、CRM 报价体系重构、批次/序列号库存、BOM 成本卷积、往来核销明细表。
- 第一批不新增数据库迁移，部署时无需 alembic。
