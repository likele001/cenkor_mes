"""
CenkorMES 演示数据生成脚本
--------------------------
运行方式：cd backend && python3 -m scripts.demo_data
或：PYTHONPATH=. python3 scripts/demo_data.py
（宝塔/部分 Linux 无 python 命令，需用 python3 或项目虚拟环境里 python）

自动创建一个完整演示工厂的数据闭环：
  租户 → 用户 → 产品/SKU → 工序 → 工艺路线 → 工价
  → 客户 → 订单 → 工单/任务 → 报工 → 审核 → 工资

幂等：检测到数据已存在时跳过，不会重复创建。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import User, user_roles
from app.models.role import Role
from app.models.department import Department
from app.models.product import Product
from app.models.sku import Sku
from app.models.process import Process
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.models.process_price import ProcessPrice
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.work_order import WorkOrder
from app.models.task import Task
from app.models.report import Report, ReportAudit
from app.models.salary import SalaryItem
from app.crud.print_template import ensure_print_template
from app.crud.customer_product import set_customer_products


SKIP_IF_EXISTS = True


def log(msg: str) -> None:
    print(f"  [DEMO] {msg}")


def get_or_create(session: Session, model_cls, unique_filter: dict, create_kwargs: dict):
    stmt = select(model_cls)
    for k, v in unique_filter.items():
        stmt = stmt.where(getattr(model_cls, k) == v)
    existing = session.scalar(stmt)
    if existing and SKIP_IF_EXISTS:
        return existing, False
    if existing:
        return existing, False
    obj = model_cls(**create_kwargs)
    session.add(obj)
    session.flush()
    return obj, True


def run():
    db: Session = SessionLocal()
    try:
        log("开始生成演示数据...")
        created = 0

        # ── 1. 租户 ──
        tenant, ok = get_or_create(db, Tenant, {"code": "DEMO"}, {
            "code": "DEMO", "name": "演示工厂",
        })
        if ok: created += 1; log(f"创建租户: {tenant.name}")
        tid = tenant.id

        # ── 2. 角色 ──
        roles = {}
        for code, name in [("admin", "管理员"), ("leader", "班组长"), ("employee", "员工"), ("customer", "客户")]:
            r, ok = get_or_create(db, Role, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
            })
            if ok: created += 1; log(f"创建角色: {name}")
            roles[code] = r

        # ── 3. 部门 ──
        dept, ok = get_or_create(db, Department, {"tenant_id": tid, "code": "D01"}, {
            "tenant_id": tid, "code": "D01", "name": "生产一部", "is_active": True,
        })
        if ok: created += 1; log(f"创建部门: {dept.name}")

        # ── 4. 用户 ──
        users = {}
        demo_users = [
            ("admin", "admin123", "系统管理员", "admin"),
            ("zhang", "123456", "张组长", "leader"),
            ("li", "123456", "李员工", "employee"),
            ("wang", "123456", "王质检", "admin"),
            ("customer1", "123456", "张老板", "customer"),
        ]
        for username, pw, full_name, role_code in demo_users:
            u, ok = get_or_create(db, User, {"tenant_id": tid, "username": username}, {
                "tenant_id": tid, "username": username,
                "password_hash": hash_password(pw),
                "full_name": full_name,
                "is_active": True,
            })
            if ok:
                created += 1
                log(f"创建用户: {full_name} ({username}/{pw})")
                if role_code in roles:
                    db.execute(user_roles.delete().where(user_roles.c.user_id == u.id))
                    db.execute(user_roles.insert().values(user_id=u.id, role_id=roles[role_code].id))
                    db.flush()
            users[username] = u
        admin_user = users["admin"]

        # ── 5. 产品 ──
        product, ok = get_or_create(db, Product, {"tenant_id": tid, "code": "P001"}, {
            "tenant_id": tid, "code": "P001", "name": "铝合金支架",
            "category": "五金件", "unit": "个", "description": "标准铝合金支架", "is_active": True,
        })
        if ok: created += 1; log(f"创建产品: {product.name}")

        # ── 6. SKU ──
        skus_data = [
            ("SKU001", "银色标准款", "银色", "铝合金6061", "100x50x5mm"),
            ("SKU002", "黑色加厚款", "黑色", "铝合金6063", "120x60x8mm"),
            ("SKU003", "蓝色防腐蚀款", "蓝色", "不锈钢304", "100x50x5mm"),
        ]
        skus = []
        for code, name, color, material, spec in skus_data:
            s, ok = get_or_create(db, Sku, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "product_id": product.id,
                "code": code, "name": name,
                "color": color, "material": material, "spec": spec,
                "is_active": True,
            })
            if ok: created += 1; log(f"创建型号: {s.name}")
            skus.append(s)

        # ── 7. 工序 ──
        processes_data = [
            ("OP01", "下料", "金工车间", 15),
            ("OP02", "冲压", "冲压车间", 10),
            ("OP03", "焊接", "焊接车间", 20),
            ("OP04", "打磨", "打磨车间", 12),
            ("OP05", "表面处理", "涂装车间", 25),
            ("OP06", "质检", "质检车间", 8),
        ]
        processes = []
        for code, name, workshop, minutes in processes_data:
            p, ok = get_or_create(db, Process, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
                "workshop": workshop, "std_minutes": minutes, "is_active": True,
            })
            if ok: created += 1; log(f"创建工序: {p.name}")
            processes.append(p)

        # ── 8. 工艺路线 ──
        route, ok = get_or_create(db, ProcessRoute, {"tenant_id": tid, "product_id": product.id, "name": "默认路线"}, {
            "tenant_id": tid, "product_id": product.id, "name": "默认路线",
            "is_active": True, "is_default": True,
        })
        if ok:
            created += 1
            log(f"创建工艺路线: {route.name}")
            for i, p in enumerate(processes, start=1):
                step = ProcessRouteStep(tenant_id=tid, route_id=route.id, seq=i, process_id=p.id)
                db.add(step)
                db.flush()

        # ── 9. 工序工价 ──
        prices = {1: 0.50, 2: 0.80, 3: 1.20, 4: 0.60, 5: 1.50, 6: 0.30}
        for sku in skus:
            for i, proc in enumerate(processes):
                idx = i + 1
                pp, ok = get_or_create(db, ProcessPrice, {
                    "tenant_id": tid, "sku_id": sku.id, "process_id": proc.id,
                }, {
                    "tenant_id": tid, "sku_id": sku.id, "process_id": proc.id,
                    "unit_price": str(prices.get(idx, 1.0)),
                    "is_active": True,
                })
                if ok: created += 1

        # ── 10. 客户 ──
        customer, ok = get_or_create(db, Customer, {"tenant_id": tid, "code": "C001"}, {
            "tenant_id": tid, "code": "C001", "name": "华强电子",
            "contact_name": "张老板", "contact_phone": "13800138001",
            "address": "深圳市南山区科技园", "is_active": True,
        })
        if ok: created += 1; log(f"创建客户: {customer.name}")

        customer2, ok = get_or_create(db, Customer, {"tenant_id": tid, "code": "C002"}, {
            "tenant_id": tid, "code": "C002", "name": "明达五金",
            "contact_name": "李明", "contact_phone": "13800138002",
            "address": "东莞市长安镇工业区", "is_active": True,
        })
        if ok: created += 1; log(f"创建客户: {customer2.name}")

        # ── 10.5 绑定客户登录账号 & 可下单产品（幂等补全）──
        cust_user = users.get("customer1")
        if cust_user and customer.user_id != cust_user.id:
            customer.user_id = cust_user.id
            db.flush()
            log(f"绑定客户账号: customer1 → {customer.name} ({customer.code})")
        product_ids = set_customer_products(db, tenant_id=tid, customer_id=customer.id, product_ids=[product.id])
        if product_ids:
            log(f"配置可下单产品: {product.name}（客户 {customer.code}）")

        # ── 11. 演示订单 ──
        orders_to_create = [
            ("ORD-DEMO-001", customer.id, skus[0].id, 100),
            ("ORD-DEMO-002", customer.id, skus[1].id, 50),
            ("ORD-DEMO-003", customer2.id, skus[2].id, 200),
        ]
        work_orders_created = 0
        for code, cust_id, sku_id, qty in orders_to_create:
            ord_obj, ok = get_or_create(db, Order, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "customer_id": cust_id, "code": code,
                "status": "confirmed", "due_date": datetime.now().date() + timedelta(days=14),
                "remark": "演示订单",
            })
            if ok:
                created += 1
                log(f"创建订单: {code} (数量 {qty})")
                oi = OrderItem(tenant_id=tid, order_id=ord_obj.id, line_no=1, sku_id=sku_id, qty=qty)
                db.add(oi)
                db.flush()
                wo = WorkOrder(tenant_id=tid, order_id=ord_obj.id, order_item_id=oi.id,
                               product_id=product.id, sku_id=sku_id, qty=qty, status="in_progress")
                db.add(wo)
                db.flush()
                work_orders_created += 1
                for i, proc in enumerate(processes):
                    task_code = f"TK{tid:03d}{work_orders_created:03d}{i+1:03d}"
                    task = Task(
                        tenant_id=tid, work_order_id=wo.id, process_id=proc.id,
                        seq=i + 1, task_code=task_code, planned_qty=qty,
                        status="done" if i < 3 else ("working" if i == 3 else "pending"),
                        assigned_user_id=users["li"].id,
                    )
                    db.add(task)
                    db.flush()

                    if i < 3:
                        good_qty = qty - (2 if i == 0 else 1)
                        bad_qty = 2 if i == 0 else 1
                        report = Report(
                            tenant_id=tid, task_id=task.id,
                            report_user_id=users["li"].id,
                            good_qty=good_qty, bad_qty=bad_qty,
                            remark="演示报工", status="qc_approved",
                        )
                        db.add(report)
                        db.flush()

                        db.add(ReportAudit(tenant_id=tid, report_id=report.id,
                                           auditor_id=users["zhang"].id, audit_level="leader",
                                           action="approve", reason=None))
                        db.add(ReportAudit(tenant_id=tid, report_id=report.id,
                                           auditor_id=users["wang"].id, audit_level="qc",
                                           action="approve", reason=None))
                        db.flush()

                        price_row = db.scalar(
                            select(ProcessPrice).where(
                                ProcessPrice.tenant_id == tid,
                                ProcessPrice.sku_id == sku_id,
                                ProcessPrice.process_id == proc.id,
                                ProcessPrice.is_active.is_(True),
                            )
                        )
                        if price_row:
                            up = Decimal(str(price_row.unit_price))
                            amt = Decimal(str(good_qty)) * up
                            db.add(SalaryItem(
                                tenant_id=tid, report_id=report.id,
                                user_id=users["li"].id, sku_id=sku_id,
                                process_id=proc.id,
                                unit_price=up, good_qty=good_qty,
                                amount=amt,
                                month=datetime.now().strftime("%Y-%m"),
                            ))
                            db.flush()

        ensure_print_template(db, tenant_id=tid, code="task_label")
        log("打印模板: task_label（任务码标签）")

        db.commit()
        log(f"\n✅ 演示数据生成完成！共创建/跳过 {created} 项。")
        log(f"\n账号信息（租户 code: DEMO）：")
        log(f"  管理员: admin / admin123")
        log(f"  班组长: zhang / 123456")
        log(f"  员工:   li    / 123456")
        log(f"  质检:   wang  / 123456")
        log(f"  客户:   customer1 / 123456")
        log(f"\n客户自助下单：客户登录后使用 H5 端")

    except Exception as e:
        db.rollback()
        log(f"❌ 出错: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
