# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0023_warehouse_bin_batch - 库区/库位/批次账/调拨单

把 lightmes 2.5 起的库位化仓储能力搬到单用户版，一共六张表：

- `warehouse_zone`      库区（存储/收货/拣货/待检/不良/发货）
- `warehouse_location`  库位（可挂库区，可 parent_id 自嵌套成货架/货位）
- `stock_batch`         批次库存，一仓一库位一型号一批次一行
- `stock_ledger`        批次流水（正=入 负=出），FIFO 与追溯的原始凭证
- `stock_transfer`      调拨单主表
- `stock_transfer_item` 调拨单明细

**为什么保留 tenant_id（单用户版明明不跑多租户）**

库里已有 `tenants` 表且只有一条 `id=1, code=cenkor`，同时
`app/models/user.py` 里 `User.tenant_id` 是固定返回 1 的 property。
保留这一列后，这六张表可以和 lightmes 共用同一份模型与服务代码，
拓展包（stock_check / warehouse_insight / stock_transfer）也不必为
「宿主有没有 tenant_id」写两套分支。代价是每条业务查询都要带
`tenant_id == 1`，比去租户化改 1400 行服务代码便宜得多。

**为什么 stock_batch.location_id 是 NOT NULL**

MySQL 唯一索引里 NULL 互不相等：`(tenant,wh,loc,sku,batch_no)` 的
location_id 一旦允许 NULL，这个唯一键对「无库位批次」完全失效，
并发入库会产生重复批次行、库存被重复计。业务上也不存在无库位批次 ——
`fifo.receive()` 未指定库位时会自动落到各仓的 DEFAULT 库位
（由紧随其后的数据初始化脚本创建）。

**为什么不建 stock_checks / stock_check_items**

cenkormes 已有 `stocktakes` / `stocktake_items`（迁移 0016），盘点主流程
归它管；拓展 stock_check 是在它之上做批次口径增强，不需要第二套盘点单。

幂等说明：DDL 直接取模型元数据（与 0013 同一套做法），新库走 0001 的
create_all 时这些表已经在了，这里 has_table 直接跳过；存量库只补建表，
不碰任何现有表与数据。

Revision ID: 0023_warehouse_bin_batch
Revises: 0022_customer_price_tiers
Create Date: 2026-11-15
"""
import sqlalchemy as sa

from alembic import op

revision = "0023_warehouse_bin_batch"
down_revision = "0022_customer_price_tiers"
branch_labels = None
depends_on = None

# 按依赖顺序列出（被引用方在前）。不用 metadata.sorted_tables：
# warehouse_location.parent_id 是自引用，全量排序会绕进去。
_NEW_TABLES = [
    "warehouse_zone",
    "warehouse_location",
    "stock_batch",
    "stock_ledger",
    "stock_transfer",
    "stock_transfer_item",
]


def upgrade() -> None:
    from app.models.base import Base

    # 只导入仓储模块，避免把无关模型的表一起拖进 metadata
    import app.models.warehouse  # noqa: F401

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _NEW_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None:
            raise RuntimeError(
                f"模型未注册 {name}：app/models/warehouse.py 是否已导入 app.models? "
                "alembic/env.py 需要 import app.models 才能拿到表定义"
            )
        if insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in reversed(_NEW_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
