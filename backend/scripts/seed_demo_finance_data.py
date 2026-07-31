"""
CenkorMES 老板看板演示数据填充脚本
--------------------------------

为 DEMO 租户（tenant_code=DEMO）补齐 5 大财务/经营指标所依赖的演示数据：
  1. orders.amount / cost_amount：订单销售额与成本
  2. orders.actual_completed_at：完成时间（用于交付率）
  3. work_orders.standard_hours / actual_hours：工时（用于产能利用率）
  4. finance_ledgers：财务台账（用于回款率）

幂等：运行前会检查是否已填充，已填充则跳过。

运行方式（backend 目录下）：
  source .venv/bin/activate
  python3 -m scripts.seed_demo_finance_data

或：
  PYTHONPATH=. python3 scripts/seed_demo_finance_data.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.finance_ledger import FinanceLedger
from app.models.order import Order, OrderItem
from app.models.work_order import WorkOrder

DEMO_TENANT_ID = 2  # tenants 表里 DEMO 的 id（运行时会自动校验）

# 单价（按 line_no 顺序 / 订单 id 顺序 循环分配）
UNIT_PRICES = [
    Decimal("128.00"),   # SKU 1：电子件
    Decimal("86.50"),    # SKU 2：五金件
    Decimal("56.00"),    # SKU 3：标准件
    Decimal("215.00"),   # SKU 4：定制件
    Decimal("320.00"),   # SKU 5：高端件
]

# 成本率（金额 * 成本率 = 成本）
COST_RATIO = Decimal("0.62")  # 平均毛利率 38%

# 产能利用率：标准工时（按工单）
STD_HOURS_PER_WO = [8.0, 12.0, 16.0, 6.0, 10.0, 14.0, 20.0, 9.0, 7.0, 11.0, 13.0, 15.0, 5.0]
# 实际工时占比（实际/标准），整体控制在 80%~95%
ACTUAL_RATIO_RANGE = (0.80, 0.95)


def _get_tenant_id(db: Session) -> int:
    """从 tenants 表里查找 DEMO 租户"""
    row = db.execute(
        text("SELECT id FROM tenants WHERE code = 'DEMO' LIMIT 1")
    ).first()
    if not row:
        raise SystemExit("ERROR: tenants 表里没有 code='DEMO' 的租户")
    return int(row[0])


def _is_already_seeded(db: Session, tenant_id: int) -> bool:
    """检测是否已填充（任一表已有非零数据即视为已 seed）"""
    has_amount = db.execute(
        text("SELECT COUNT(*) FROM orders WHERE tenant_id=:t AND amount > 0"),
        {"t": tenant_id},
    ).scalar() or 0
    has_std = db.execute(
        text("SELECT COUNT(*) FROM work_orders WHERE tenant_id=:t AND standard_hours > 0"),
        {"t": tenant_id},
    ).scalar() or 0
    has_ledger = db.execute(
        text("SELECT COUNT(*) FROM finance_ledgers WHERE tenant_id=:t"),
        {"t": tenant_id},
    ).scalar() or 0
    return (has_amount + has_std + has_ledger) > 0


def seed_orders(db: Session, tenant_id: int) -> int:
    """为 orders 补 amount / cost_amount / actual_completed_at"""
    orders = db.execute(
        select(Order)
        .where(Order.tenant_id == tenant_id)
        .order_by(Order.id)
    ).scalars().all()

    if not orders:
        return 0

    n_updated = 0
    for idx, order in enumerate(orders):
        # 1) 计算订单金额 = SUM(order_items.qty * unit_price)
        items = db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).scalars().all()
        if not items:
            continue
        amount = Decimal("0")
        for i, item in enumerate(items):
            unit_price = UNIT_PRICES[(idx + i) % len(UNIT_PRICES)]
            amount += unit_price * Decimal(item.qty)
            # 同步更新 order_items 自身的 unit_price / subtotal
            item.unit_price = unit_price
            item.subtotal = unit_price * Decimal(item.qty)

        order.amount = amount.quantize(Decimal("0.01"))
        order.cost_amount = (amount * COST_RATIO).quantize(Decimal("0.01"))

        # 2) 把最早的几个订单标记为 completed / shipped（带 actual_completed_at）
        if idx < 4 and order.status == "producing" and order.due_date is not None:
            order.status = "completed"
            # 在 due_date 之前 1~3 天完成
            offset_days = (idx % 3)  # 0,1,2 天提前
            comp_dt = datetime.combine(order.due_date, time(10, 0)) - timedelta(days=offset_days)
            order.actual_completed_at = comp_dt
        elif idx < 7 and order.status == "producing":
            # 5/6 号订单标为 shipped
            order.status = "shipped"
            order.actual_completed_at = (order.confirmed_at or datetime.now()) + timedelta(days=idx + 1)

        n_updated += 1

    return n_updated


def seed_work_orders(db: Session, tenant_id: int) -> int:
    """为 work_orders 补 standard_hours / actual_hours"""
    wos = db.execute(
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id)
        .order_by(WorkOrder.id)
    ).scalars().all()

    if not wos:
        return 0

    n_updated = 0
    for idx, wo in enumerate(wos):
        std_h = STD_HOURS_PER_WO[idx % len(STD_HOURS_PER_WO)]
        wo.standard_hours = Decimal(str(std_h))
        # 实际工时在 80%~95% 之间
        ratio = ACTUAL_RATIO_RANGE[0] + (idx * 0.013) % (ACTUAL_RATIO_RANGE[1] - ACTUAL_RATIO_RANGE[0])
        wo.actual_hours = Decimal(str(round(std_h * ratio, 2)))

        # 设置时间戳
        if wo.status == "in_progress" and wo.started_at is None:
            wo.started_at = datetime.now() - timedelta(days=idx + 1)
        elif wo.status == "completed" and wo.finished_at is None:
            wo.started_at = datetime.now() - timedelta(days=idx + 3)
            wo.finished_at = datetime.now() - timedelta(days=idx + 1)

        n_updated += 1

    return n_updated


def seed_finance_ledgers(db: Session, tenant_id: int) -> int:
    """为 finance_ledgers 补充回款与支出记录

    规则：
    - 每张已 completed/shipped 的订单配 1~2 条 direction=in 的回款（incoming）
    - 同时插入若干 direction=out 的采购/费用支出，营造真实账本
    """
    # 拉取订单
    orders = db.execute(
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.status.in_(("completed", "shipped", "producing", "confirmed")),
        )
        .order_by(Order.confirmed_at)
    ).scalars().all()

    if not orders:
        return 0

    now = datetime.now()
    n_inserted = 0

    # ---- 1) 销售回款 ----
    for idx, order in enumerate(orders):
        # 60% 的订单一次性回款 100% 金额，30% 回 70%，10% 还没回
        ratio_map = [Decimal("1.00"), Decimal("0.70"), Decimal("1.00"), Decimal("0.70"), Decimal("0.30")]
        ratio = ratio_map[idx % len(ratio_map)]
        if ratio == 0:
            continue
        amount = (Decimal(str(order.amount)) * ratio).quantize(Decimal("0.01"))
        # 回款日期：订单确认后 7~20 天
        biz_date = (order.confirmed_at or now).date() + timedelta(days=7 + (idx % 14))
        if biz_date > now.date():
            biz_date = now.date() - timedelta(days=(idx % 5) + 1)

        ledger = FinanceLedger(
            tenant_id=tenant_id,
            direction="in",
            category="sales",
            party_type="customer",
            party_id=order.customer_id,
            statement_type="order",
            statement_id=order.id,
            amount=amount,
            biz_date=biz_date,
            remark=f"回款 {ratio * 100:.0f}% - {order.code}",
            created_by=None,
        )
        db.add(ledger)
        n_inserted += 1

    # ---- 2) 采购支出（制造费用） ----
    purchase_amounts = [
        Decimal("15000.00"),
        Decimal("8500.50"),
        Decimal("12300.00"),
        Decimal("6800.00"),
        Decimal("4200.00"),
    ]
    for idx, amt in enumerate(purchase_amounts):
        biz_date = now.date() - timedelta(days=(idx + 1) * 4)
        db.add(FinanceLedger(
            tenant_id=tenant_id,
            direction="out",
            category="purchase",
            party_type="supplier",
            party_id=None,
            statement_type=None,
            statement_id=None,
            amount=amt,
            biz_date=biz_date,
            remark=f"原材料采购 #{idx + 1}",
        ))
        n_inserted += 1

    # ---- 3) 运营费用（水电、租金、工资） ----
    expense_amounts = [
        (Decimal("8500.00"), "厂房租金 5月"),
        (Decimal("3200.00"), "水电费 5月"),
        (Decimal("2800.00"), "水电费 6月"),
        (Decimal("12000.00"), "车间工资 5月"),
        (Decimal("12000.00"), "车间工资 6月"),
        (Decimal("1600.00"), "设备维护"),
    ]
    for idx, (amt, remark) in enumerate(expense_amounts):
        biz_date = now.date() - timedelta(days=(idx + 1) * 5)
        db.add(FinanceLedger(
            tenant_id=tenant_id,
            direction="out",
            category="expense",
            party_type="other",
            party_id=None,
            statement_type=None,
            statement_id=None,
            amount=amt,
            biz_date=biz_date,
            remark=remark,
        ))
        n_inserted += 1

    return n_inserted


def main():
    db: Session = SessionLocal()
    try:
        tenant_id = _get_tenant_id(db)
        print(f"[INFO] DEMO tenant_id = {tenant_id}")

        if _is_already_seeded(db, tenant_id):
            print("[SKIP] 已检测到演示数据，跳过 seed（若需重置，请先清空相关表）")
            print("       清空命令：")
            print("         DELETE FROM finance_ledgers WHERE tenant_id=2;")
            print("         UPDATE orders SET amount=0, cost_amount=0, actual_completed_at=NULL, status='producing' WHERE tenant_id=2;")
            print("         UPDATE order_items SET unit_price=0, subtotal=0 WHERE tenant_id=2;")
            print("         UPDATE work_orders SET standard_hours=0, actual_hours=0, started_at=NULL, finished_at=NULL WHERE tenant_id=2;")
            return

        n_orders = seed_orders(db, tenant_id)
        print(f"[OK ] orders  更新 {n_orders} 个（含 amount / cost_amount / status / actual_completed_at）")

        n_wos = seed_work_orders(db, tenant_id)
        print(f"[OK ] work_orders 更新 {n_wos} 个（含 standard_hours / actual_hours）")

        n_ledgers = seed_finance_ledgers(db, tenant_id)
        print(f"[OK ] finance_ledgers 新增 {n_ledgers} 条（销售回款 + 采购支出 + 运营费用）")

        db.commit()
        print("[DONE] 演示数据填充完成。请刷新老板看板页面查看 5 大指标。")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
