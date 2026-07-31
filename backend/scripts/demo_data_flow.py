#!/usr/bin/env python3
"""
CenkorMES 完整流程演示数据生成脚本
==================================
运行方式：cd backend && python3 scripts/demo_data_flow.py

单租户全流程闭环：
  客户自助下单 → 后台审核 → 齐套检查(缺料) → 自动采购 → 生产计划
  → 任务分工 → 员工报工 → 班组长审核 → 质检审核
  → 溯源码 → 自动计件工资 → 成本利润分析

所有数据 100% 属于同一个租户 DEMO_FLOW，不混用任何其他租户数据。
幂等：检测到数据已存在时跳过，不会重复创建。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
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
from app.models.customer_product import CustomerProduct
from app.models.order import Order, OrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_piece import WorkOrderPiece
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.report import Report, ReportAudit
from app.models.salary import SalaryItem
from app.models.salary_slip import SalarySlip
from app.models.salary_allowance import SalaryAllowance
from app.models.material import Supplier, Material, MaterialBom, MaterialBomItem
from app.models.warehouse import Warehouse, Stock, StockLog
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.trace import TraceCode
from app.models.quality import InspectionTemplate, InspectionTemplateItem, DefectCode, InspectionRecord
from app.models.production_plan import ProductionPlan
from app.models.plan_purchase_link import PlanPurchaseLink
from app.models.finance_ledger import FinanceLedger
from app.models.equipment import Equipment
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.crud.print_template import ensure_print_template
from app.crud.rbac import create_default_roles_for_tenant

SKIP_IF_EXISTS = True
TENANT_CODE = "DEMO_FLOW"
TODAY = date.today()
CURRENT_MONTH = TODAY.strftime("%Y-%m")


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
        log("=" * 60)
        log("  CenkorMES 完整流程演示数据生成")
        log("  租户: DEMO_FLOW | 单订单全流程闭环")
        log("=" * 60)
        created = 0

        # ════════════════════════════════════════════════════════════
        # 1. 租户
        # ════════════════════════════════════════════════════════════
        log("\n── 1. 创建租户 ──")
        tenant, ok = get_or_create(db, Tenant, {"code": TENANT_CODE}, {
            "code": TENANT_CODE, "name": "流程演示工厂",
        })
        if ok:
            created += 1
            log(f"  租户: {tenant.name} (code={TENANT_CODE})")
        tid = tenant.id

        # ════════════════════════════════════════════════════════════
        # 2. 角色
        # ════════════════════════════════════════════════════════════
        log("\n── 2. 创建角色 ──")
        roles = {}
        for code, name in [
            ("admin", "管理员"), ("leader", "班组长"),
            ("employee", "员工"), ("qc", "质检员"), ("customer", "客户"),
        ]:
            r, ok = get_or_create(db, Role, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
            })
            if ok:
                created += 1
                log(f"  角色: {name}")
            roles[code] = r

        # 为角色分配权限
        log("  分配角色权限...")
        create_default_roles_for_tenant(db, tid)
        log("  权限分配完成")

        # ════════════════════════════════════════════════════════════
        # 3. 部门
        # ════════════════════════════════════════════════════════════
        log("\n── 3. 创建部门 ──")
        depts = {}
        for code, name in [
            ("D01", "生产部"), ("D02", "质检部"),
            ("D03", "仓储部"), ("D04", "财务部"),
        ]:
            d, ok = get_or_create(db, Department, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name, "is_active": True,
            })
            if ok:
                created += 1
                log(f"  部门: {name}")
            depts[code] = d

        # ════════════════════════════════════════════════════════════
        # 4. 用户（全部属于 DEMO_FLOW 租户）
        # ════════════════════════════════════════════════════════════
        log("\n── 4. 创建用户 ──")
        users = {}
        demo_users = [
            ("admin_flow", "admin123", "系统管理员", "admin", "D01"),
            ("manager_flow", "123456", "李主管", "admin", "D01"),
            ("zhang_flow", "123456", "张组长", "leader", "D01"),
            ("li_flow", "123456", "李员工", "employee", "D01"),
            ("zhao_flow", "123456", "赵员工", "employee", "D01"),
            ("qian_flow", "123456", "钱员工", "employee", "D01"),
            ("wang_flow", "123456", "王质检", "qc", "D02"),
            ("chen_flow", "123456", "陈仓管", "employee", "D03"),
            ("customer_flow", "123456", "张老板", "customer", None),
        ]
        for username, pw, full_name, role_code, dept_code in demo_users:
            kwargs = {
                "tenant_id": tid, "username": username,
                "password_hash": hash_password(pw),
                "full_name": full_name, "is_active": True,
            }
            if dept_code and dept_code in depts:
                kwargs["department_id"] = depts[dept_code].id
            u, ok = get_or_create(db, User, {"tenant_id": tid, "username": username}, kwargs)
            if ok:
                created += 1
                log(f"  用户: {full_name} ({username}/{pw})")
                if role_code in roles:
                    db.execute(user_roles.delete().where(user_roles.c.user_id == u.id))
                    db.execute(user_roles.insert().values(user_id=u.id, role_id=roles[role_code].id))
                    db.flush()
            users[username] = u

        admin_user = users["admin_flow"]
        manager_user = users["manager_flow"]
        zhang_user = users["zhang_flow"]
        li_user = users["li_flow"]
        zhao_user = users["zhao_flow"]
        qian_user = users["qian_flow"]
        wang_user = users["wang_flow"]
        chen_user = users["chen_flow"]
        customer_user = users["customer_flow"]

        # ════════════════════════════════════════════════════════════
        # 5. 产品
        # ════════════════════════════════════════════════════════════
        log("\n── 5. 创建产品 ──")
        product, ok = get_or_create(db, Product, {"tenant_id": tid, "code": "P001"}, {
            "tenant_id": tid, "code": "P001", "name": "铝合金支架",
            "category": "五金件", "unit": "个",
            "description": "标准铝合金支架，用于电子设备固定", "is_active": True,
        })
        if ok:
            created += 1
            log(f"  产品: {product.name} ({product.code})")

        # ════════════════════════════════════════════════════════════
        # 6. SKU（产品型号 + 物料SKU）
        # ════════════════════════════════════════════════════════════
        log("\n── 6. 创建产品型号(SKU) ──")
        sku, ok = get_or_create(db, Sku, {"tenant_id": tid, "code": "SKU001"}, {
            "tenant_id": tid, "product_id": product.id,
            "code": "SKU001", "name": "银色标准款",
            "color": "银色", "material": "铝合金6061", "spec": "100x50x5mm",
            "is_active": True,
        })
        if ok:
            created += 1
            log(f"  型号: {sku.name} ({sku.code})")

        # 物料也需要各自 SKU（materials 表 uq_materials_tenant_sku 约束）
        material_skus = {}
        for code, name in [
            ("SKU-MAT001", "铝板材6061"), ("SKU-MAT002", "不锈钢焊条"),
            ("SKU-MAT003", "砂纸"), ("SKU-MAT004", "粉末涂料"),
        ]:
            ms, ok = get_or_create(db, Sku, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "product_id": product.id,
                "code": code, "name": name, "is_active": True,
            })
            if ok:
                created += 1
                log(f"  物料SKU: {name} ({code})")
            material_skus[code] = ms

        # ════════════════════════════════════════════════════════════
        # 7. 工序
        # ════════════════════════════════════════════════════════════
        log("\n── 7. 创建生产工序 ──")
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
            if ok:
                created += 1
                log(f"  工序: {p.name} ({p.code}) | 车间: {workshop} | 标准工时: {minutes}min")
            processes.append(p)

        # ════════════════════════════════════════════════════════════
        # 8. 工艺路线
        # ════════════════════════════════════════════════════════════
        log("\n── 8. 创建工艺路线 ──")
        route, ok = get_or_create(db, ProcessRoute, {
            "tenant_id": tid, "product_id": product.id, "name": "默认路线"
        }, {
            "tenant_id": tid, "product_id": product.id, "name": "默认路线",
            "is_active": True, "is_default": True,
        })
        if ok:
            created += 1
            log(f"  工艺路线: {route.name}")
            for i, p in enumerate(processes, start=1):
                step = ProcessRouteStep(tenant_id=tid, route_id=route.id, seq=i, process_id=p.id)
                db.add(step)
                db.flush()
            log(f"  路线步骤: {len(processes)} 道工序")

        # ════════════════════════════════════════════════════════════
        # 9. 工序工价（SKU × 工序）
        # ════════════════════════════════════════════════════════════
        log("\n── 9. 配置工序工价 ──")
        prices_map = {1: 0.50, 2: 0.80, 3: 1.20, 4: 0.60, 5: 1.50, 6: 0.30}
        process_prices = {}
        for i, proc in enumerate(processes):
            idx = i + 1
            pp, ok = get_or_create(db, ProcessPrice, {
                "tenant_id": tid, "sku_id": sku.id, "process_id": proc.id,
            }, {
                "tenant_id": tid, "sku_id": sku.id, "process_id": proc.id,
                "unit_price": str(prices_map.get(idx, 1.0)),
                "is_active": True,
            })
            if ok:
                created += 1
                log(f"  工价: {sku.name} × {proc.name} = ¥{prices_map[idx]}/件")
            process_prices[proc.id] = pp

        # ════════════════════════════════════════════════════════════
        # 10. 设备
        # ════════════════════════════════════════════════════════════
        log("\n── 10. 创建设备 ──")
        equipment_list = []
        for code, name, model, workshop in [
            ("EQ01", "数控剪板机", "QC12K-4×2500", "金工车间"),
            ("EQ02", "冲压机", "J23-25", "冲压车间"),
            ("EQ03", "氩弧焊机", "WSM-315", "焊接车间"),
            ("EQ04", "角磨机", "SIM-FF-100A", "打磨车间"),
            ("EQ05", "喷涂设备", "HY-800", "涂装车间"),
        ]:
            eq, ok = get_or_create(db, Equipment, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
                "model": model, "workshop": workshop, "status": "active",
            })
            if ok:
                created += 1
                log(f"  设备: {name} ({code})")
            equipment_list.append(eq)

        # ════════════════════════════════════════════════════════════
        # 11. 供应商
        # ════════════════════════════════════════════════════════════
        log("\n── 11. 创建供应商 ──")
        supplier, ok = get_or_create(db, Supplier, {"tenant_id": tid, "code": "SUP001"}, {
            "tenant_id": tid, "code": "SUP001", "name": "鑫达铝材有限公司",
            "contact_name": "王经理", "phone": "13900139001",
            "address": "佛山市南海区铝材市场", "is_active": True,
        })
        if ok:
            created += 1
            log(f"  供应商: {supplier.name}")

        # ════════════════════════════════════════════════════════════
        # 12. 物料
        # ════════════════════════════════════════════════════════════
        log("\n── 12. 创建物料 ──")
        materials = {}
        mat_sku_map = [
            ("MAT001", "铝板材6061", "kg", "3mm×1000mm×2000mm", "SKU-MAT001"),
            ("MAT002", "不锈钢焊条", "根", "Φ2.5mm×300mm", "SKU-MAT002"),
            ("MAT003", "砂纸", "张", "240目", "SKU-MAT003"),
            ("MAT004", "粉末涂料", "kg", "银色RAL9006", "SKU-MAT004"),
        ]
        for code, name, unit, spec, sku_code in mat_sku_map:
            m, ok = get_or_create(db, Material, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
                "unit": unit, "spec": spec,
                "supplier_id": supplier.id, "sku_id": material_skus[sku_code].id, "is_active": True,
            })
            if ok:
                created += 1
                log(f"  物料: {name} ({code})")
            materials[code] = m

        # ════════════════════════════════════════════════════════════
        # 13. BOM（物料清单）
        # ════════════════════════════════════════════════════════════
        log("\n── 13. 创建BOM物料清单 ──")
        bom, ok = get_or_create(db, MaterialBom, {
            "tenant_id": tid, "sku_id": sku.id, "scope": "sku"
        }, {
            "tenant_id": tid, "scope": "sku",
            "product_id": product.id, "sku_id": sku.id,
            "name": f"{sku.name} BOM", "version": 1,
            "is_default": True, "is_active": True,
            "created_by": admin_user.id,
        })
        if ok:
            created += 1
            log(f"  BOM: {bom.name}")
            bom_items_data = [
                (materials["MAT001"], 1),   # 1kg 铝板/件
                (materials["MAT002"], 2),   # 2根焊条/件
                (materials["MAT003"], 1),   # 1张砂纸/件
                (materials["MAT004"], 1),   # 1kg 粉末涂料/件
            ]
            for mat, qty_per in bom_items_data:
                item = MaterialBomItem(
                    tenant_id=tid, bom_id=bom.id,
                    material_id=mat.id, qty_per=qty_per,
                )
                db.add(item)
                db.flush()
            log(f"  BOM明细: {len(bom_items_data)} 项物料")

        # ════════════════════════════════════════════════════════════
        # 14. 仓库
        # ════════════════════════════════════════════════════════════
        log("\n── 14. 创建仓库 ──")
        warehouses = {}
        for code, name, addr in [
            ("WH01", "原材料仓", "A栋1楼"),
            ("WH02", "半成品仓", "A栋2楼"),
            ("WH03", "成品仓", "B栋1楼"),
        ]:
            w, ok = get_or_create(db, Warehouse, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name, "address": addr, "is_active": True,
            })
            if ok:
                created += 1
                log(f"  仓库: {name} ({code})")
            warehouses[code] = w

        # ════════════════════════════════════════════════════════════
        # 15. 初始库存（制造缺料场景）
        # ════════════════════════════════════════════════════════════
        log("\n── 15. 设置初始库存（缺料场景）──")
        # 订单需要 100 个产品 → 铝板需要 100kg，库存只有 50kg（缺 50kg）
        wh01_id = warehouses["WH01"].id
        mat_sku_aluminum = material_skus["SKU-MAT001"]
        s, ok = get_or_create(db, Stock, {
            "tenant_id": tid, "warehouse_id": wh01_id, "sku_id": mat_sku_aluminum.id,
        }, {
            "tenant_id": tid, "warehouse_id": wh01_id,
            "sku_id": mat_sku_aluminum.id, "qty": 50,  # 铝板库存 50kg（缺料场景）
        })
        if ok:
            created += 1
            log(f"  库存: 原材料(铝板) = 50kg ⚠️ 缺料! (需要100kg)")

        # ════════════════════════════════════════════════════════════
        # 16. 客户
        # ════════════════════════════════════════════════════════════
        log("\n── 16. 创建客户 ──")
        customer, ok = get_or_create(db, Customer, {"tenant_id": tid, "code": "C001"}, {
            "tenant_id": tid, "code": "C001", "name": "华强电子有限公司",
            "contact_name": "张老板", "contact_phone": "13800138001",
            "address": "深圳市南山区科技园", "is_active": True,
        })
        if ok:
            created += 1
            log(f"  客户: {customer.name}")

        # 绑定客户登录账号
        if customer.user_id != customer_user.id:
            customer.user_id = customer_user.id
            db.flush()
            log(f"  绑定客户账号: customer_flow → {customer.name}")

        # 配置客户可下单产品
        cp_exists = db.scalar(
            select(CustomerProduct).where(
                CustomerProduct.tenant_id == tid,
                CustomerProduct.customer_id == customer.id,
                CustomerProduct.product_id == product.id,
            )
        )
        if not cp_exists:
            db.add(CustomerProduct(tenant_id=tid, customer_id=customer.id, product_id=product.id))
            db.flush()
            created += 1
            log(f"  配置可下单产品: {product.name}")

        # ════════════════════════════════════════════════════════════
        # 17. 订单（客户下单 → 管理员确认）
        # ════════════════════════════════════════════════════════════
        log("\n── 17. 创建订单（客户下单 → 后台确认）──")
        ORDER_CODE = "ORD-FLOW-001"
        ORDER_QTY = 100
        order, ok = get_or_create(db, Order, {"tenant_id": tid, "code": ORDER_CODE}, {
            "tenant_id": tid, "customer_id": customer.id,
            "code": ORDER_CODE,
            "status": "confirmed",
            "due_date": TODAY + timedelta(days=14),
            "remark": "演示订单 - 铝合金支架 100个",
            "confirmed_at": datetime.now(),
            "confirmed_by": manager_user.id,
        })
        if ok:
            created += 1
            log(f"  订单: {ORDER_CODE} | 状态: 已确认 | 交期: {order.due_date}")

        oi, ok = get_or_create(db, OrderItem, {
            "tenant_id": tid, "order_id": order.id, "line_no": 1
        }, {
            "tenant_id": tid, "order_id": order.id, "line_no": 1,
            "sku_id": sku.id, "qty": ORDER_QTY,
        })
        if ok:
            created += 1
            log(f"  订单明细: {sku.name} × {ORDER_QTY}个")

        # ════════════════════════════════════════════════════════════
        # 18. 齐套检查 → 采购（缺料自动采购）
        # ════════════════════════════════════════════════════════════
        log("\n── 18. 齐套检查 & 自动采购 ──")
        log(f"  订单需求: {ORDER_QTY}个 × 铝板1kg/个 = 需要 {ORDER_QTY}kg 铝板")
        log(f"  当前库存: 铝板 50kg → 缺料 {ORDER_QTY - 50}kg")
        log(f"  → 自动创建采购单...")

        PURCHASE_CODE = "PO-FLOW-001"
        po, ok = get_or_create(db, PurchaseOrder, {"tenant_id": tid, "code": PURCHASE_CODE}, {
            "tenant_id": tid, "supplier_id": supplier.id,
            "code": PURCHASE_CODE,
            "status": "confirmed",
            "remark": f"齐套检查缺料自动采购 - 铝板 {ORDER_QTY - 50}kg",
            "confirmed_at": datetime.now(),
            "confirmed_by": manager_user.id,
            "created_by": manager_user.id,
        })
        if ok:
            created += 1
            log(f"  采购单: {PURCHASE_CODE} | 状态: 已确认")

        poi, ok = get_or_create(db, PurchaseOrderItem, {
            "tenant_id": tid, "order_id": po.id, "material_id": materials["MAT001"].id,
        }, {
            "tenant_id": tid, "order_id": po.id,
            "material_id": materials["MAT001"].id,
            "qty": ORDER_QTY - 50,
            "received_qty": ORDER_QTY - 50,  # 已收货
            "unit_price": Decimal("20.00"),
        })
        if ok:
            created += 1
            log(f"  采购明细: 铝板 {ORDER_QTY - 50}kg × ¥20 = ¥{(ORDER_QTY - 50) * 20}")

        # 采购收货 → 库存更新
        mat_stock = db.scalar(
            select(Stock).where(
                Stock.tenant_id == tid,
                Stock.warehouse_id == wh01_id,
                Stock.sku_id == mat_sku_aluminum.id,
            )
        )
        if mat_stock:
            mat_stock.qty += (ORDER_QTY - 50)
            db.flush()
            log(f"  收货入库: 铝板 +{ORDER_QTY - 50}kg → 当前库存 {mat_stock.qty}kg ✅")

        # 库存流水
        sl_exists = db.scalar(
            select(StockLog).where(
                StockLog.tenant_id == tid,
                StockLog.biz_type == "purchase_in",
                StockLog.biz_id == po.id,
            )
        )
        if not sl_exists:
            db.add(StockLog(
                tenant_id=tid, warehouse_id=wh01_id,
                sku_id=mat_sku_aluminum.id,
                change_qty=ORDER_QTY - 50,
                balance_qty=mat_stock.qty if mat_stock else ORDER_QTY,
                biz_type="purchase_in", biz_id=po.id,
                remark=f"采购收货 {PURCHASE_CODE}",
            ))
            db.flush()

        # ════════════════════════════════════════════════════════════
        # 19. 生产计划
        # ════════════════════════════════════════════════════════════
        log("\n── 19. 创建生产计划 ──")
        plan, ok = get_or_create(db, ProductionPlan, {"tenant_id": tid, "code": "PLAN-FLOW-001"}, {
            "tenant_id": tid, "order_id": order.id,
            "code": "PLAN-FLOW-001",
            "status": "released",
            "start_date": TODAY + timedelta(days=1),
            "end_date": TODAY + timedelta(days=10),
            "work_days": 8,
            "remark": f"铝合金支架 {ORDER_QTY}个 生产计划",
            "created_by": manager_user.id,
            "released_at": datetime.now(),
            "released_by": manager_user.id,
        })
        if ok:
            created += 1
            log(f"  生产计划: {plan.code} | {plan.start_date} ~ {plan.end_date} | 状态: 已下达")

        # 计划-采购关联
        link_exists = db.scalar(
            select(PlanPurchaseLink).where(
                PlanPurchaseLink.tenant_id == tid,
                PlanPurchaseLink.plan_id == plan.id,
                PlanPurchaseLink.purchase_order_id == po.id,
            )
        )
        if not link_exists:
            db.add(PlanPurchaseLink(
                tenant_id=tid, plan_id=plan.id, purchase_order_id=po.id,
            ))
            db.flush()

        # ════════════════════════════════════════════════════════════
        # 20. 工单
        # ════════════════════════════════════════════════════════════
        log("\n── 20. 创建工单 ──")
        wo, ok = get_or_create(db, WorkOrder, {
            "tenant_id": tid, "order_item_id": oi.id,
        }, {
            "tenant_id": tid, "order_id": order.id, "order_item_id": oi.id,
            "product_id": product.id, "sku_id": sku.id,
            "qty": ORDER_QTY, "status": "in_progress",
        })
        if ok:
            created += 1
            log(f"  工单: WO-{wo.id} | {sku.name} × {ORDER_QTY} | 状态: 生产中")

        # ════════════════════════════════════════════════════════════
        # 21. 工单件次（一物一码基础）
        # ════════════════════════════════════════════════════════════
        log("\n── 21. 创建工单件次 ──")
        piece_count = 0
        for pn in range(1, ORDER_QTY + 1):
            pc, ok = get_or_create(db, WorkOrderPiece, {
                "tenant_id": tid, "work_order_id": wo.id, "piece_no": pn,
            }, {
                "tenant_id": tid, "work_order_id": wo.id,
                "piece_no": pn,
                "product_code": f"PC-{ORDER_CODE}-{pn:04d}",
                "status": "in_progress",
            })
            if ok:
                piece_count += 1
        if piece_count:
            created += piece_count
            log(f"  件次: {piece_count} 个产品码已生成")

        # ════════════════════════════════════════════════════════════
        # 22. 任务分工（派工）
        # ════════════════════════════════════════════════════════════
        log("\n── 22. 任务分工（派工）──")
        # 工序 → 员工映射
        task_assign_map = [
            (processes[0], li_user, "下料"),     # 李员工：下料
            (processes[1], li_user, "冲压"),     # 李员工：冲压
            (processes[2], zhao_user, "焊接"),   # 赵员工：焊接
            (processes[3], zhao_user, "打磨"),   # 赵员工：打磨
            (processes[4], qian_user, "表面处理"), # 钱员工：表面处理
            (processes[5], wang_user, "质检"),   # 王质检：质检
        ]

        tasks_created = []
        for i, (proc, emp, proc_name) in enumerate(task_assign_map):
            seq = i + 1
            task_code = f"TK-FLOW-{seq:03d}"
            t, ok = get_or_create(db, Task, {"tenant_id": tid, "task_code": task_code}, {
                "tenant_id": tid, "work_order_id": wo.id,
                "process_id": proc.id, "seq": seq,
                "task_code": task_code, "planned_qty": ORDER_QTY,
                "status": "done",  # 全部完成
                "assigned_user_id": emp.id,
                "assigned_at": datetime.now(),
                "assigned_by": manager_user.id,
            })
            if ok:
                created += 1
                log(f"  任务: {task_code} | {proc_name} → {emp.full_name} | 计划 {ORDER_QTY}件")
            tasks_created.append(t)

            # TaskAssignment 明细
            ta_exists = db.scalar(
                select(TaskAssignment).where(
                    TaskAssignment.tenant_id == tid,
                    TaskAssignment.task_id == t.id,
                    TaskAssignment.user_id == emp.id,
                )
            )
            if not ta_exists:
                db.add(TaskAssignment(
                    tenant_id=tid, task_id=t.id,
                    user_id=emp.id, assigned_qty=ORDER_QTY,
                    assigned_at=datetime.now(),
                    assigned_by=manager_user.id,
                ))
                db.flush()

        # ════════════════════════════════════════════════════════════
        # 23. 报工（员工报工 → 含不良品）
        # ════════════════════════════════════════════════════════════
        log("\n── 23. 员工报工 ──")
        # 每道工序报工数据：合格数、不良数
        report_data = [
            (tasks_created[0], li_user, 98, 2, "下料完成，2件尺寸偏差"),
            (tasks_created[1], li_user, 97, 1, "冲压完成，1件模具偏移"),
            (tasks_created[2], zhao_user, 96, 1, "焊接完成，1件虚焊"),
            (tasks_created[3], zhao_user, 96, 0, "打磨完成"),
            (tasks_created[4], qian_user, 95, 1, "表面处理完成，1件色差"),
            (tasks_created[5], wang_user, 95, 0, "质检完成，合格95件"),
        ]

        reports_created = []
        for task, emp, good, bad, remark in report_data:
            r, ok = get_or_create(db, Report, {
                "tenant_id": tid, "task_id": task.id,
            }, {
                "tenant_id": tid, "task_id": task.id,
                "report_user_id": emp.id,
                "good_qty": good, "bad_qty": bad,
                "remark": remark,
                "status": "qc_approved",  # 直接已审核通过
            })
            if ok:
                created += 1
                log(f"  报工: {task.process.name} | 合格 {good} | 不良 {bad} | {emp.full_name}")
            reports_created.append(r)

        # ════════════════════════════════════════════════════════════
        # 24. 审核（班组长初审 + 质检终审）
        # ════════════════════════════════════════════════════════════
        log("\n── 24. 两级审核 ──")
        for r in reports_created:
            # 班组长初审
            aud1_exists = db.scalar(
                select(ReportAudit).where(
                    ReportAudit.tenant_id == tid,
                    ReportAudit.report_id == r.id,
                    ReportAudit.audit_level == "leader",
                )
            )
            if not aud1_exists:
                db.add(ReportAudit(
                    tenant_id=tid, report_id=r.id,
                    auditor_id=zhang_user.id, audit_level="leader",
                    action="approve", reason=None,
                ))
                db.flush()

            # 质检终审
            aud2_exists = db.scalar(
                select(ReportAudit).where(
                    ReportAudit.tenant_id == tid,
                    ReportAudit.report_id == r.id,
                    ReportAudit.audit_level == "qc",
                )
            )
            if not aud2_exists:
                db.add(ReportAudit(
                    tenant_id=tid, report_id=r.id,
                    auditor_id=wang_user.id, audit_level="qc",
                    action="approve", reason=None,
                ))
                db.flush()

            log(f"  审核: 报工#{r.id} | 张组长初审 ✓ → 王质检终审 ✓")

        # ════════════════════════════════════════════════════════════
        # 25. 质检模板 & 缺陷代码
        # ════════════════════════════════════════════════════════════
        log("\n── 25. 质检模板 & 缺陷代码 ──")

        # 缺陷代码
        defect_codes_data = [
            ("DEF01", "气孔", "major", "焊接表面气孔缺陷"),
            ("DEF02", "虚焊", "critical", "焊点未充分熔合"),
            ("DEF03", "划痕", "minor", "表面划伤"),
            ("DEF04", "色差", "minor", "涂层颜色不一致"),
            ("DEF05", "尺寸偏差", "major", "尺寸超出公差范围"),
        ]
        defect_codes = {}
        for code, name, severity, desc in defect_codes_data:
            dc, ok = get_or_create(db, DefectCode, {"tenant_id": tid, "code": code}, {
                "tenant_id": tid, "code": code, "name": name,
                "severity": severity, "description": desc, "is_active": True,
            })
            if ok:
                created += 1
                log(f"  缺陷代码: {name} ({code}) [{severity}]")
            defect_codes[code] = dc

        # 质检模板
        insp_template, ok = get_or_create(db, InspectionTemplate, {
            "tenant_id": tid, "code": "QC-WELD"
        }, {
            "tenant_id": tid, "code": "QC-WELD",
            "name": "焊接工序检查项",
            "description": "焊接质量检查标准",
            "process_id": processes[2].id,  # 焊接工序
            "product_id": product.id,
            "is_active": True,
        })
        if ok:
            created += 1
            log(f"  质检模板: {insp_template.name}")

            template_items_data = [
                (1, "焊缝外观", "pass_fail", None, None, None, None),
                (2, "焊点强度", "pass_fail", None, None, None, None),
                (3, "焊接尺寸", "measure", "100", "102", "98", "mm"),
                (4, "表面气孔", "pass_fail", None, None, None, None),
            ]
            for seq, name, itype, sv, ul, ll, unit in template_items_data:
                item = InspectionTemplateItem(
                    template_id=insp_template.id,
                    seq=seq, item_name=name, item_type=itype,
                    standard_value=sv, upper_limit=ul, lower_limit=ll,
                    unit=unit, is_required=True,
                )
                db.add(item)
                db.flush()
            log(f"  模板明细: {len(template_items_data)} 项检查项")

        # ════════════════════════════════════════════════════════════
        # 26. 溯源码（一物一码）
        # ════════════════════════════════════════════════════════════
        log("\n── 26. 生成溯源码 ──")
        # 获取所有件次
        pieces = db.scalars(
            select(WorkOrderPiece).where(
                WorkOrderPiece.tenant_id == tid,
                WorkOrderPiece.work_order_id == wo.id,
            ).order_by(WorkOrderPiece.piece_no)
        ).all()

        trace_count = 0
        for piece in pieces:
            for task in tasks_created:
                # 每件每工序生成一条溯源记录
                report_for_task = next((r for r in reports_created if r.task_id == task.id), None)
                trace_code_str = f"TC-{piece.product_code}-{task.seq:02d}"
                tc_exists = db.scalar(
                    select(TraceCode).where(
                        TraceCode.tenant_id == tid,
                        TraceCode.code == trace_code_str,
                    )
                )
                if not tc_exists:
                    db.add(TraceCode(
                        tenant_id=tid,
                        code=trace_code_str,
                        product_code=piece.product_code,
                        work_order_id=wo.id,
                        piece_id=piece.id,
                        task_seq=task.seq,
                        order_id=order.id,
                        sku_id=sku.id,
                        process_id=task.process_id,
                        report_id=report_for_task.id if report_for_task else None,
                        user_id=task.assigned_user_id or li_user.id,
                        qty=1,
                    ))
                    trace_count += 1

        if trace_count:
            created += trace_count
            log(f"  溯源码: {trace_count} 条记录 ({ORDER_QTY}件 × {len(tasks_created)}工序)")

        # ════════════════════════════════════════════════════════════
        # 27. 自动计件工资
        # ════════════════════════════════════════════════════════════
        log("\n── 27. 自动计件工资 ──")
        salary_total = Decimal("0")
        salary_by_user = {}

        for r in reports_created:
            task = next((t for t in tasks_created if t.id == r.task_id), None)
            if not task:
                continue

            pp = db.scalar(
                select(ProcessPrice).where(
                    ProcessPrice.tenant_id == tid,
                    ProcessPrice.sku_id == sku.id,
                    ProcessPrice.process_id == task.process_id,
                    ProcessPrice.is_active.is_(True),
                )
            )
            if not pp:
                continue

            unit_price = Decimal(str(pp.unit_price))
            amount = Decimal(str(r.good_qty)) * unit_price

            si_exists = db.scalar(
                select(SalaryItem).where(
                    SalaryItem.tenant_id == tid,
                    SalaryItem.report_id == r.id,
                )
            )
            if not si_exists:
                db.add(SalaryItem(
                    tenant_id=tid, report_id=r.id,
                    user_id=r.report_user_id, sku_id=sku.id,
                    process_id=task.process_id,
                    unit_price=unit_price, good_qty=r.good_qty,
                    amount=amount, month=CURRENT_MONTH,
                ))
                db.flush()
                created += 1

                uid = r.report_user_id
                if uid not in salary_by_user:
                    salary_by_user[uid] = Decimal("0")
                salary_by_user[uid] += amount
                salary_total += amount

                log(f"  工资: {task.process.name} | 合格{r.good_qty}件 × ¥{unit_price} = ¥{amount}")

        log(f"  计件工资合计: ¥{salary_total}")

        # ════════════════════════════════════════════════════════════
        # 28. 工资条 & 补贴扣款
        # ════════════════════════════════════════════════════════════
        log("\n── 28. 工资条 & 补贴扣款 ──")
        for uid, item_amount in salary_by_user.items():
            emp = next((u for uname, u in users.items() if u.id == uid), None)
            if not emp:
                continue

            # 补贴
            bonus = Decimal("200.00") if emp.full_name in ["李员工", "赵员工"] else Decimal("0")
            deduction = Decimal("0")

            slip_exists = db.scalar(
                select(SalarySlip).where(
                    SalarySlip.tenant_id == tid,
                    SalarySlip.user_id == uid,
                    SalarySlip.month == CURRENT_MONTH,
                )
            )
            if not slip_exists:
                # 计算总件数
                total_qty = sum(r.good_qty for r in reports_created if r.report_user_id == uid)
                net = item_amount + bonus - deduction
                db.add(SalarySlip(
                    tenant_id=tid, user_id=uid, month=CURRENT_MONTH,
                    item_amount=item_amount, bonus_amount=bonus,
                    deduction_amount=deduction, net_amount=net,
                    total_qty=total_qty,
                ))
                db.flush()
                created += 1
                log(f"  工资条: {emp.full_name} | 计件 ¥{item_amount} + 补贴 ¥{bonus} = 实发 ¥{net}")

            # 补贴记录
            if bonus > 0:
                allow_exists = db.scalar(
                    select(SalaryAllowance).where(
                        SalaryAllowance.tenant_id == tid,
                        SalaryAllowance.user_id == uid,
                        SalaryAllowance.month == CURRENT_MONTH,
                        SalaryAllowance.allowance_type == "bonus",
                    )
                )
                if not allow_exists:
                    db.add(SalaryAllowance(
                        tenant_id=tid, user_id=uid,
                        allowance_type="bonus", amount=bonus,
                        month=CURRENT_MONTH, reason="全勤奖",
                        created_by=admin_user.id,
                    ))
                    db.flush()

        # ════════════════════════════════════════════════════════════
        # 29. 财务流水（成本分析）
        # ════════════════════════════════════════════════════════════
        log("\n── 29. 财务流水 & 成本分析 ──")

        # 采购支出
        purchase_cost = Decimal(str(ORDER_QTY - 50)) * Decimal("20.00")
        fl1_exists = db.scalar(
            select(FinanceLedger).where(
                FinanceLedger.tenant_id == tid,
                FinanceLedger.statement_type == "purchase",
                FinanceLedger.statement_id == po.id,
            )
        )
        if not fl1_exists:
            db.add(FinanceLedger(
                tenant_id=tid, direction="out", category="material",
                party_type="supplier", party_id=supplier.id,
                statement_type="purchase", statement_id=po.id,
                amount=purchase_cost, biz_date=TODAY,
                remark=f"采购铝板 {ORDER_QTY - 50}kg",
                created_by=manager_user.id,
            ))
            db.flush()
            log(f"  支出: 采购铝板 ¥{purchase_cost}")

        # 人工成本
        labor_cost = salary_total
        fl2_exists = db.scalar(
            select(FinanceLedger).where(
                FinanceLedger.tenant_id == tid,
                FinanceLedger.category == "labor",
                FinanceLedger.remark.like(f"%{ORDER_CODE}%"),
            )
        )
        if not fl2_exists:
            db.add(FinanceLedger(
                tenant_id=tid, direction="out", category="labor",
                party_type="employee", party_id=None,
                amount=labor_cost, biz_date=TODAY,
                remark=f"计件工资 {ORDER_CODE}",
                created_by=admin_user.id,
            ))
            db.flush()
            log(f"  支出: 人工成本 ¥{labor_cost}")

        # 销售收入（假设售价 ¥15/个）
        sell_price = Decimal("15.00")
        revenue = Decimal(str(ORDER_QTY)) * sell_price
        fl3_exists = db.scalar(
            select(FinanceLedger).where(
                FinanceLedger.tenant_id == tid,
                FinanceLedger.category == "sales",
                FinanceLedger.remark.like(f"%{ORDER_CODE}%"),
            )
        )
        if not fl3_exists:
            db.add(FinanceLedger(
                tenant_id=tid, direction="in", category="sales",
                party_type="customer", party_id=customer.id,
                amount=revenue, biz_date=TODAY,
                remark=f"销售收入 {ORDER_CODE} | {ORDER_QTY}个 × ¥{sell_price}",
                created_by=admin_user.id,
            ))
            db.flush()
            log(f"  收入: 销售收入 ¥{revenue}")

        # 成本利润汇总
        total_cost = purchase_cost + labor_cost
        profit = revenue - total_cost
        margin = (profit / revenue * 100) if revenue > 0 else Decimal("0")
        log(f"\n  ╔══════════════════════════════════╗")
        log(f"  ║  成本利润分析                    ║")
        log(f"  ╠══════════════════════════════════╣")
        log(f"  ║  销售收入: ¥{revenue:>10.2f}          ║")
        log(f"  ║  物料成本: ¥{purchase_cost:>10.2f}          ║")
        log(f"  ║  人工成本: ¥{labor_cost:>10.2f}          ║")
        log(f"  ║  ─────────────────────────       ║")
        log(f"  ║  总成本:   ¥{total_cost:>10.2f}          ║")
        log(f"  ║  毛利润:   ¥{profit:>10.2f}          ║")
        log(f"  ║  毛利率:   {margin:.1f}%                  ║")
        log(f"  ╚══════════════════════════════════╝")

        # ════════════════════════════════════════════════════════════
        # 30. 打印模板
        # ════════════════════════════════════════════════════════════
        log("\n── 30. 打印模板 ──")
        ensure_print_template(db, tenant_id=tid, code="task_label")
        log("  打印模板: task_label（任务码标签）")

        # ════════════════════════════════════════════════════════════
        # 提交
        # ════════════════════════════════════════════════════════════
        db.commit()

        log("\n" + "=" * 60)
        log("  ✅ 完整流程演示数据生成完成！")
        log("=" * 60)
        log(f"\n  📋 租户信息: code={TENANT_CODE}, 名称=流程演示工厂")
        log(f"\n  👤 账号信息:")
        log(f"    管理员1:  admin_flow    / admin123")
        log(f"    管理员2:  manager_flow  / 123456  (生产主管)")
        log(f"    班组长:   zhang_flow    / 123456")
        log(f"    员工:     li_flow       / 123456  (下料/冲压)")
        log(f"    员工:     zhao_flow     / 123456  (焊接/打磨)")
        log(f"    员工:     qian_flow     / 123456  (表面处理)")
        log(f"    质检:     wang_flow     / 123456")
        log(f"    仓管:     chen_flow     / 123456")
        log(f"    客户:     customer_flow / 123456  (张老板)")
        log(f"\n  📦 核心数据:")
        log(f"    订单:     {ORDER_CODE} | {sku.name} × {ORDER_QTY}个")
        log(f"    采购单:   {PURCHASE_CODE} | 铝板 {ORDER_QTY - 50}kg")
        log(f"    生产计划: PLAN-FLOW-001")
        log(f"    溯源码:   {trace_count} 条")
        log(f"    工资合计: ¥{salary_total}")
        log(f"    毛利润:   ¥{profit}")
        log(f"\n  🔄 完整流程:")
        log(f"    客户下单 → 后台确认 → 齐套检查(缺料)")
        log(f"    → 自动采购 → 采购收货 → 生产计划")
        log(f"    → 任务分工 → 员工报工 → 班组长审核")
        log(f"    → 质检终审 → 溯源码 → 自动计件工资")
        log(f"    → 成本利润分析")
        log(f"\n  💡 提示: 客户自助下单请使用 H5 端登录 customer_flow")

    except Exception as e:
        db.rollback()
        log(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
