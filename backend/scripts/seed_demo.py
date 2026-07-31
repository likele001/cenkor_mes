#!/usr/bin/env python3
"""
CenkorMES 演示数据 seed 脚本
生成完整的业务闭环演示数据：客户→订单→工单→任务→报工→质检→工资+CRM+考勤

用法:
  cd /www/wwwroot/cenkormes/backend
  python scripts/seed_demo.py

所有演示账号密码: 123456
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timedelta, time
from decimal import Decimal
import random
import bcrypt

from sqlalchemy import text
from app.core.db import SessionLocal
from app.models import *
from app.models.crm import (
    CustomerContact, CrmOpportunity, CrmOpportunityActivity,
    CustomerTag, CustomerTagLink, CrmLead, CrmLeadActivity,
    CrmQuotation, CrmQuotationItem, CrmContract, CrmPaymentPlan,
    CrmWinLossReason, CrmCampaign, CrmCampaignMember, CrmSalesTarget,
)

random.seed(42)
TENANT_ID = 1
D = Decimal

def pw():
    return bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode("ascii")

NOW = datetime.now()
TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")
LAST_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

def d(days_ago=0):
    return TODAY - timedelta(days=days_ago)

def dt(days_ago=0, hour=8, minute=0):
    return datetime(TODAY.year, TODAY.month, TODAY.day, hour, minute) - timedelta(days=days_ago)

def main():
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(User).filter(User.username == "wangjianguo").first()
        if existing:
            print(f"[SKIP] 演示数据已存在，跳过（如需重新生成请先清空数据库）")
            return

        print("=" * 60)
        print("  CenkorMES 演示数据生成")
        print("=" * 60)

        # ── Phase 1: Foundation ──────────────────────────
        print("\n[1/11] 部门...")
        depts = seed_departments(db)

        print("[2/11] 角色与权限...")
        roles, perms = seed_roles_permissions(db)

        print("[3/11] 用户...")
        users = seed_users(db, depts, roles)

        print("[4/11] 技能...")
        skills = seed_skills(db, users)

        # ── Phase 2: Product & Process ───────────────────
        print("[5/11] 产品与工序...")
        products, skus, processes, routes, prices = seed_products_processes(db)

        # ── Phase 3: Equipment & Materials ───────────────
        print("[6/11] 设备与物料...")
        equip = seed_equipment_materials(db, skus, processes, users)

        # ── Phase 4: Customer & CRM ──────────────────────
        print("[7/11] 客户与CRM...")
        customers = seed_customers_crm(db, users, skus)

        # ── Phase 5: Orders & Production ─────────────────
        print("[8/11] 订单与生产...")
        orders_data = seed_orders_production(db, customers, skus, routes, processes, users, equip, prices)

        # ── Phase 6: Tasks, Reports, Quality ─────────────
        print("[9/11] 任务/报工/质检...")
        seed_tasks_reports_quality(db, orders_data, users, processes, prices, equip)

        # ── Phase 7: Salary ──────────────────────────────
        print("[10/11] 工资与考勤...")
        seed_salary_attendance(db, users, prices)

        # ── Phase 8: Support data ────────────────────────
        print("[11/11] 通知/字典/其他...")
        seed_support(db, users, customers)

        db.commit()
        print("\n" + "=" * 60)
        print("  演示数据生成完成！")
        print("  所有账号密码: 123456")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


# ════════════════════════════════════════════════════════════
#  Phase 1: Foundation
# ════════════════════════════════════════════════════════════

def seed_departments(db):
    # Check if demo departments already created
    demo_check = db.query(Department).filter(Department.code == "PROD").first()
    if demo_check:
        return {d.code: d for d in db.query(Department).all()}

    depts = {}
    # Root department
    root = db.query(Department).filter(Department.code == "HQ").first()
    if not root:
        root = Department(code="HQ", name="辰科工装制造有限公司", is_active=True)
        db.add(root); db.flush()
    depts["HQ"] = root

    depts_list = [
        ("PROD", "生产部", root.id),
        ("QC", "质检部", root.id),
        ("WH", "仓储部", root.id),
        ("SALES", "销售部", root.id),
        ("HR", "行政人事部", root.id),
    ]
    for code, name, pid in depts_list:
        dep = Department(code=code, name=name, parent_id=pid, is_active=True)
        db.add(dep); db.flush()
        depts[code] = dep

    # Workshops under production
    workshops = [
        ("WS_CUT", "裁剪车间", depts["PROD"].id),
        ("WS_SEW", "缝制车间", depts["PROD"].id),
        ("WS_FIN", "后整车间", depts["PROD"].id),
    ]
    for code, name, pid in workshops:
        dep = Department(code=code, name=name, parent_id=pid, is_active=True)
        db.add(dep); db.flush()
        depts[code] = dep

    db.flush()
    return depts


def seed_roles_permissions(db):
    # Check if demo roles already created
    demo_check = db.query(Role).filter(Role.code == "production_manager").first()
    if demo_check:
        roles = {r.code: r for r in db.query(Role).all()}
        perms = {p.code: p for p in db.query(Permission).all()}
        return roles, perms

    # Permissions
    perm_codes = [
        ("admin.access", "系统管理"),
        ("dashboard.view", "数据看板"),
        ("order.view", "查看订单"), ("order.create", "创建订单"), ("order.edit", "编辑订单"),
        ("workorder.view", "查看工单"), ("workorder.manage", "管理工单"),
        ("task.view", "查看任务"), ("task.assign", "分配任务"),
        ("report.view", "查看报工"), ("report.submit", "提交报工"), ("report.approve", "审批报工"),
        ("qc.inspect", "质检操作"), ("qc.approve", "质检审批"),
        ("salary.view", "查看工资"), ("salary.manage", "工资管理"),
        ("customer.view", "查看客户"), ("customer.manage", "管理客户"),
        ("crm.sales", "CRM销售"), ("crm.admin", "CRM管理"),
        ("warehouse.view", "查看库存"), ("warehouse.manage", "库存管理"),
        ("equipment.view", "查看设备"), ("equipment.manage", "设备管理"),
        ("production.plan", "生产计划"),
        ("ai.use", "AI功能"), ("ai.alert.view", "AI预警"),
        ("customer.order.view", "客户查看订单"),
        ("customer.orderDetail.view", "客户查看订单详情"),
        ("customer.orderProgress.view", "客户查看订单进度"),
        ("customer.statements.view", "客户查看对账单"),
        ("customer.statementDetail.view", "客户查看对账单详情"),
    ]
    perms = {}
    for code, name in perm_codes:
        existing_p = db.query(Permission).filter(Permission.code == code).first()
        if existing_p:
            perms[code] = existing_p
        else:
            p = Permission(code=code, name=name)
            db.add(p); db.flush()
            perms[code] = p

    # Roles
    role_defs = [
        ("admin", "超级管理员", list(perms.keys())),
        ("production_manager", "生产经理", [
            "dashboard.view", "order.view", "order.create", "order.edit",
            "workorder.view", "workorder.manage", "task.view", "task.assign",
            "report.view", "report.approve", "production.plan",
            "equipment.view", "equipment.manage", "warehouse.view",
        ]),
        ("workshop_leader", "车间组长", [
            "dashboard.view", "order.view", "workorder.view",
            "task.view", "task.assign", "report.view", "report.submit", "report.approve",
        ]),
        ("worker", "生产工人", [
            "task.view", "report.submit", "salary.view",
        ]),
        ("qc_inspector", "质检员", [
            "report.view", "qc.inspect", "qc.approve", "dashboard.view",
        ]),
        ("sales_rep", "销售代表", [
            "dashboard.view", "order.view", "order.create", "order.edit",
            "customer.view", "customer.manage", "crm.sales",
        ]),
        ("warehouse_keeper", "仓管员", [
            "warehouse.view", "warehouse.manage", "dashboard.view",
        ]),
        ("hr_admin", "人事专员", [
            "dashboard.view", "salary.view", "salary.manage",
        ]),
        ("customer", "客户账号", [
            "customer.order.view", "customer.orderDetail.view",
            "customer.orderProgress.view", "customer.statements.view",
            "customer.statementDetail.view",
        ]),
    ]
    roles = {}
    for code, name, perm_list in role_defs:
        existing_r = db.query(Role).filter(Role.code == code).first()
        if existing_r:
            roles[code] = existing_r
        else:
            r = Role(code=code, name=name)
            db.add(r); db.flush()
            roles[code] = r
        for pc in perm_list:
            if pc in perms:
                db.execute(text(
                    "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"
                ), {"r": roles[code].id, "p": perms[pc].id})

    db.flush()
    return roles, perms


def seed_users(db, depts, roles):
    # Check if demo users already seeded
    existing = db.query(User).filter(User.username == "wangjianguo").first()
    if existing:
        return {u.username: u for u in db.query(User).all()}

    password = pw()
    user_defs = [
        # (username, full_name, dept_code, role_code, salary_type, hourly_rate)
        ("admin", "系统管理员", "HQ", "admin", "hourly", None),
        ("wangjianguo", "王建国", "PROD", "production_manager", "hourly", None),
        ("lizhiqiang", "李志强", "WS_CUT", "workshop_leader", "piece", None),
        ("zhangwei", "张伟", "WS_SEW", "workshop_leader", "piece", None),
        ("chenming", "陈明", "WS_FIN", "workshop_leader", "piece", None),
        ("liuyang", "刘洋", "WS_CUT", "worker", "piece", None),
        ("zhaojing", "赵静", "WS_CUT", "worker", "piece", None),
        ("sunli", "孙丽", "WS_SEW", "worker", "piece", None),
        ("zhoufang", "周芳", "WS_SEW", "worker", "piece", None),
        ("wulei", "吴磊", "WS_SEW", "worker", "piece", None),
        ("zhengpeng", "郑鹏", "WS_FIN", "worker", "piece", None),
        ("huangting", "黄婷", "WS_FIN", "worker", "piece", None),
        ("hemin", "何敏", "QC", "qc_inspector", "hourly", None),
        ("linfeng", "林峰", "SALES", "sales_rep", "hourly", None),
        ("xuna", "许娜", "WH", "warehouse_keeper", "hourly", None),
        ("yangjie", "杨洁", "HR", "hr_admin", "hourly", None),
    ]

    users = {}
    for uname, full_name, dept_code, role_code, stype, hrate in user_defs:
        existing_u = db.query(User).filter(User.username == uname).first()
        if existing_u:
            users[uname] = existing_u
            # Update department if needed
            if dept_code in depts and existing_u.department_id != depts[dept_code].id:
                existing_u.department_id = depts[dept_code].id
            continue
        u = User(
            username=uname,
            password_hash=password,
            full_name=full_name,
            department_id=depts[dept_code].id,
            is_active=True,
            is_superuser=(uname == "admin"),
            salary_type=stype,
            hourly_rate=D(str(hrate)) if hrate else None,
            created_at=NOW,
        )
        db.add(u); db.flush()
        # Assign role
        r = roles[role_code]
        db.execute(text(
            "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (:u, :r)"
        ), {"u": u.id, "r": r.id})
        users[uname] = u

    # Customer portal accounts
    cust_users = [
        ("cust_huachen", "陈丽华", "customer"),
        ("cust_xingda", "刘大伟", "customer"),
        ("cust_yuanjing", "张雪", "customer"),
    ]
    for uname, full_name, role_code in cust_users:
        existing_u = db.query(User).filter(User.username == uname).first()
        if existing_u:
            users[uname] = existing_u
            continue
        u = User(
            username=uname, password_hash=password, full_name=full_name,
            is_active=True, salary_type="piece", created_at=NOW,
        )
        db.add(u); db.flush()
        db.execute(text(
            "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (:u, :r)"
        ), {"u": u.id, "r": roles[role_code].id})
        users[uname] = u

    db.flush()
    return users


def seed_skills(db, users):
    if db.query(Skill).count() > 0:
        return {s.code: s for s in db.query(Skill).all()}

    skill_defs = [
        ("cutting", "裁剪"), ("sewing", "缝纫"), ("ironing", "熨烫"),
        ("qc_check", "质检"), ("packaging", "包装"),
    ]
    skills = {}
    for code, name in skill_defs:
        s = Skill(code=code, name=name, is_active=True)
        db.add(s); db.flush()
        skills[code] = s

    # Link users to skills
    skill_map = {
        "lizhiqiang": ["cutting"], "liuyang": ["cutting"], "zhaojing": ["cutting"],
        "zhangwei": ["sewing"], "sunli": ["sewing"], "zhoufang": ["sewing"], "wulei": ["sewing"],
        "chenming": ["ironing", "packaging"], "zhengpeng": ["ironing"], "huangting": ["packaging"],
        "hemin": ["qc_check"],
    }
    for uname, scodes in skill_map.items():
        if uname in users:
            for sc in scodes:
                db.add(UserSkillLink(user_id=users[uname].id, skill_id=skills[sc].id))
    db.flush()
    return skills


# ════════════════════════════════════════════════════════════
#  Phase 2: Products & Processes
# ════════════════════════════════════════════════════════════

def seed_products_processes(db):
    if db.query(Product).count() > 0:
        products = {p.code: p for p in db.query(Product).all()}
        skus = {}
        for p in products.values():
            for s in db.query(Sku).filter(Sku.product_id == p.id).all():
                skus[s.code] = s
        processes = {p.code: p for p in db.query(Process).all()}
        routes = {}
        for p in products.values():
            r = db.query(ProcessRoute).filter(ProcessRoute.product_id == p.id, ProcessRoute.is_default == True).first()
            if r: routes[p.code] = r
        prices = {}
        return products, skus, processes, routes, prices

    products = {}
    product_defs = [
        ("P-GZ", "工装套装", "工装", "套"),
        ("P-FH", "防护服", "防护", "套"),
        ("P-FJ", "防静电服", "特种", "套"),
    ]
    for code, name, cat, unit in product_defs:
        p = Product(code=code, name=name, category=cat, unit=unit, is_active=True)
        db.add(p); db.flush()
        products[code] = p

    # SKUs
    skus = {}
    sku_defs = [
        ("P-GZ", [("SKU-GZ-BL-M", "工装套装-藏蓝M码", "藏蓝", "涤棉", "M", D("85.00")),
                  ("SKU-GZ-BL-L", "工装套装-藏蓝L码", "藏蓝", "涤棉", "L", D("85.00")),
                  ("SKU-GZ-GY-M", "工装套装-灰色M码", "灰色", "涤棉", "M", D("85.00"))]),
        ("P-FH", [("SKU-FH-WH-L", "防护服-白色L码", "白色", "阻燃", "L", D("120.00")),
                  ("SKU-FH-WH-XL", "防护服-白色XL码", "白色", "阻燃", "XL", D("125.00"))]),
        ("P-FJ", [("SKU-FJ-BL-M", "防静电服-蓝色M码", "蓝色", "防静电", "M", D("95.00")),
                  ("SKU-FJ-BL-L", "防静电服-蓝色L码", "蓝色", "防静电", "L", D("95.00"))]),
    ]
    for pcode, sku_list in sku_defs:
        for code, name, color, material, spec, cost in sku_list:
            s = Sku(product_id=products[pcode].id, code=code, name=name,
                    color=color, material=material, spec=spec, cost_price=cost, is_active=True)
            db.add(s); db.flush()
            skus[code] = s

    # Processes
    processes = {}
    proc_defs = [
        ("PROC-CUT", "裁剪", "裁剪车间", 30),
        ("PROC-SEW", "缝纫", "缝制车间", 60),
        ("PROC-IRON", "熨烫", "后整车间", 15),
        ("PROC-QC", "质检", "后整车间", 10),
        ("PROC-PKG", "包装", "后整车间", 8),
    ]
    for code, name, workshop, std in proc_defs:
        p = Process(code=code, name=name, workshop=workshop, std_minutes=std, is_active=True)
        db.add(p); db.flush()
        processes[code] = p

    # Process routes (default route for each product)
    routes = {}
    route_defs = {
        "P-GZ": ["PROC-CUT", "PROC-SEW", "PROC-IRON", "PROC-QC", "PROC-PKG"],
        "P-FH": ["PROC-CUT", "PROC-SEW", "PROC-QC", "PROC-PKG"],
        "P-FJ": ["PROC-CUT", "PROC-SEW", "PROC-IRON", "PROC-QC", "PROC-PKG"],
    }
    for pcode, proc_list in route_defs.items():
        r = ProcessRoute(product_id=products[pcode].id, name=f"{products[pcode].name}标准工艺", is_default=True, is_active=True)
        db.add(r); db.flush()
        routes[pcode] = r
        for seq, pc in enumerate(proc_list, 1):
            step = ProcessRouteStep(route_id=r.id, seq=seq, process_id=processes[pc].id)
            db.add(step)

    # Process prices (piece-rate per SKU+process)
    prices = {}
    price_map = {
        "SKU-GZ-BL-M": {"PROC-CUT": D("5.00"), "PROC-SEW": D("18.00"), "PROC-IRON": D("3.00"), "PROC-QC": D("2.00"), "PROC-PKG": D("1.50")},
        "SKU-GZ-BL-L": {"PROC-CUT": D("5.00"), "PROC-SEW": D("18.00"), "PROC-IRON": D("3.00"), "PROC-QC": D("2.00"), "PROC-PKG": D("1.50")},
        "SKU-GZ-GY-M": {"PROC-CUT": D("5.00"), "PROC-SEW": D("18.00"), "PROC-IRON": D("3.00"), "PROC-QC": D("2.00"), "PROC-PKG": D("1.50")},
        "SKU-FH-WH-L": {"PROC-CUT": D("6.00"), "PROC-SEW": D("25.00"), "PROC-QC": D("3.00"), "PROC-PKG": D("2.00")},
        "SKU-FH-WH-XL": {"PROC-CUT": D("6.50"), "PROC-SEW": D("26.00"), "PROC-QC": D("3.00"), "PROC-PKG": D("2.00")},
        "SKU-FJ-BL-M": {"PROC-CUT": D("5.50"), "PROC-SEW": D("20.00"), "PROC-IRON": D("3.50"), "PROC-QC": D("2.50"), "PROC-PKG": D("1.80")},
        "SKU-FJ-BL-L": {"PROC-CUT": D("5.50"), "PROC-SEW": D("20.00"), "PROC-IRON": D("3.50"), "PROC-QC": D("2.50"), "PROC-PKG": D("1.80")},
    }
    for sku_code, proc_prices in price_map.items():
        if sku_code in skus:
            for proc_code, price in proc_prices.items():
                pp = ProcessPrice(sku_id=skus[sku_code].id, process_id=processes[proc_code].id,
                                  unit_price=price, is_active=True)
                db.add(pp)
                prices[(sku_code, proc_code)] = pp

    db.flush()
    return products, skus, processes, routes, prices


# ════════════════════════════════════════════════════════════
#  Phase 3: Equipment & Materials
# ════════════════════════════════════════════════════════════

def seed_equipment_materials(db, skus, processes, users):
    if db.query(Equipment).count() > 0:
        return {e.code: e for e in db.query(Equipment).all()}

    equip_defs = [
        ("EQ-CUT-01", "自动裁床A", "JC-3000", "裁剪车间", "active"),
        ("EQ-CUT-02", "自动裁床B", "JC-3000", "裁剪车间", "active"),
        ("EQ-SEW-01", "平缝机01", "DDL-9000C", "缝制车间", "active"),
        ("EQ-SEW-02", "平缝机02", "DDL-9000C", "缝制车间", "active"),
        ("EQ-SEW-03", "包缝机01", "MO-6800D", "缝制车间", "active"),
        ("EQ-SEW-04", "包缝机02", "MO-6800D", "缝制车间", "maintenance"),
        ("EQ-IRON-01", "蒸汽熨台A", "YS-500", "后整车间", "active"),
        ("EQ-IRON-02", "蒸汽熨台B", "YS-500", "后整车间", "active"),
        ("EQ-PKG-01", "自动包装机", "BZ-200", "后整车间", "active"),
    ]
    equip = {}
    for code, name, model, workshop, status in equip_defs:
        e = Equipment(code=code, name=name, model=model, workshop=workshop,
                      status=status, purchase_date=d(365), last_maintenance_date=d(30),
                      next_maintenance_date=d(-30), maintenance_interval_days=30)
        db.add(e); db.flush()
        equip[code] = e

    # Suppliers
    suppliers = {}
    sup_defs = [
        ("SUP-FB", "鑫达面料厂", "王经理", "13800001111", "浙江省绍兴市中纺城A栋"),
        ("SUP-FZ", "永丰辅料公司", "李总", "13900002222", "广东省广州市中大布匹市场"),
        ("SUP-BZ", "华印包装材料", "张总", "13700003333", "江苏省苏州市工业园区"),
    ]
    for code, name, contact, phone, addr in sup_defs:
        s = Supplier(code=code, name=name, contact_name=contact, phone=phone, address=addr, is_active=True)
        db.add(s); db.flush()
        suppliers[code] = s

    # Materials
    materials = {}
    mat_defs = [
        ("MAT-DC", "涤棉面料", "米", "65/35 涤棉 240g", "SUP-FB", "SKU-GZ-BL-M"),
        ("MAT-ZR", "阻燃面料", "米", "Nomex IIIA 200g", "SUP-FB", "SKU-FH-WH-L"),
        ("MAT-FJ", "防静电面料", "米", "导电丝 180g", "SUP-FB", "SKU-FJ-BL-M"),
    ]
    for code, name, unit, spec, sup_code, sku_code in mat_defs:
        m = Material(
            code=code, name=name, unit=unit, spec=spec,
            supplier_id=suppliers[sup_code].id,
            sku_id=skus[sku_code].id if sku_code else None,
            is_active=True,
        )
        db.add(m); db.flush()
        materials[code] = m

    # Warehouses & Stock - skip (models not registered in __init__.py yet)
    # Can be seeded via admin panel or direct SQL later

    db.flush()
    return equip


# ════════════════════════════════════════════════════════════
#  Phase 4: Customers & CRM
# ════════════════════════════════════════════════════════════

def seed_customers_crm(db, users, skus):
    if db.query(Customer).count() > 0:
        return {c.code: c for c in db.query(Customer).all()}

    cust_defs = [
        ("C-HC", "华辰制造有限公司", "赵总", "13800138001", "重庆市渝北区金渝大道89号",
         "active", 85, "A", "none", "制造业", "large", "VIP",
         D("328000.00"), "cust_huachen", users["linfeng"].id),
        ("C-XD", "兴达建工集团", "钱经理", "13900139002", "成都市武侯区天府大道388号",
         "active", 72, "B", "none", "建筑", "large", "gold",
         D("186500.00"), "cust_xingda", users["linfeng"].id),
        ("C-YJ", "远景新能源科技", "孙总", "13700137003", "绵阳市高新区科技大道66号",
         "active", 68, "B", "none", "新能源", "medium", "silver",
         D("95200.00"), "cust_yuanjing", users["linfeng"].id),
        ("C-CG", "重庆钢铁股份", "李部长", "13600136004", "重庆市长寿区江南街道",
         "prospect", 50, "C", "none", "钢铁", "large", None,
         D("0"), None, users["linfeng"].id),
        ("C-NB", "南京生物科技", "周主任", "13500135005", "南京市江宁区生物医药谷",
         "prospect", 40, "C", "none", "生物医药", "medium", None,
         D("0"), None, users["linfeng"].id),
    ]

    customers = {}
    for (code, name, contact, phone, addr, stage, health, level, risk,
         industry, scale, cust_level, ltv, portal_user, owner_id) in cust_defs:
        c = Customer(
            code=code, name=name, contact_name=contact, contact_phone=phone, address=addr,
            lifecycle_stage=stage, health_score=health, health_level=level, risk_flag=risk,
            industry=industry, scale=scale, customer_level=cust_level,
            total_lifetime_value=ltv,
            user_id=users[portal_user].id if portal_user else None,
            owner_user_id=owner_id,
        )
        db.add(c); db.flush()
        customers[code] = c

    # CRM Tags
    tags = {}
    for tag_name in ["老客户", "大客户", "高潜力", "需跟进", "VIP"]:
        t = CustomerTag(tenant_id=TENANT_ID, name=tag_name)
        db.add(t); db.flush()
        tags[tag_name] = t
    # Link tags
    tag_links = [("C-HC", ["老客户", "大客户", "VIP"]), ("C-XD", ["老客户", "大客户"]),
                 ("C-YJ", ["老客户"]), ("C-CG", ["高潜力", "需跟进"])]
    for ccode, tnames in tag_links:
        for tname in tnames:
            db.add(CustomerTagLink(tenant_id=TENANT_ID, customer_id=customers[ccode].id, tag_id=tags[tname].id))

    # CRM Opportunities
    opp_defs = [
        ("华辰2026秋季工装采购", customers["C-HC"], users["linfeng"],
         "negotiation", "open", D("156000.00"), D("0.75"), d(-30),
         "200套工装套装+100套防护服"),
        ("兴达年度防护服框架", customers["C-XD"], users["linfeng"],
         "proposal", "open", D("280000.00"), D("0.60"), d(-45),
         "年度框架合同，预计500套防护服"),
        ("远景防静电服首批", customers["C-YJ"], users["linfeng"],
         "qualification", "open", D("47500.00"), D("0.50"), d(-60),
         "首批100套防静电服试用"),
        ("重庆钢铁防护服年度", customers["C-CG"], users["linfeng"],
         "prospecting", "open", D("520000.00"), D("0.20"), d(-90),
         "年度采购计划，正在比价阶段"),
        ("南京生物洁净服", customers["C-NB"], users["linfeng"],
         "closed_lost", "lost", D("180000.00"), D("0"), d(-15),
         "竞标失败，价格不具备优势"),
    ]
    for idx, (title, cust, owner, stage, status, amount, prob, exp_close, desc) in enumerate(opp_defs, 1):
        opp = CrmOpportunity(
            tenant_id=TENANT_ID, code=f"OPP-2026-{idx:03d}", title=title, customer_id=cust.id, owner_user_id=owner.id,
            stage=stage, status=status, amount=amount, probability=prob,
            expected_close_date=exp_close, remark=desc,
        )
        db.add(opp); db.flush()
        # Activities
        for i, (action, note) in enumerate([
            ("call", f"电话沟通{title}需求"),
            ("visit", f"现场拜访，了解具体要求"),
            ("note", f"已发送初步方案"),
        ]):
            act = CrmOpportunityActivity(
                tenant_id=TENANT_ID, opportunity_id=opp.id, action_type=action, content=note,
                created_by=owner.id, created_at=dt(20 - i * 5, 10),
            )
            db.add(act)

    # CRM Leads
    lead_defs = [
        ("武汉光电有限公司", "张采购", "13400134006", "new", 65, "B",
         "website", "对防静电服感兴趣", customers["C-CG"]),
        ("深圳半导体科技", "王总", "13300133007", "contacted", 45, "C",
         "referral", "通过老客户推荐", None),
    ]
    for idx2, (company, contact, phone, status, score, grade, source, note, cust) in enumerate(lead_defs, 1):
        lead = CrmLead(
            tenant_id=TENANT_ID, code=f"LEAD-2026-{idx2:03d}", company=company, contact_name=contact, phone=phone,
            status=status, score=score, grade=grade, source=source, remark=note,
            customer_id=cust.id if cust else None,
        )
        db.add(lead)

    # Win/Loss reasons
    for idx3, (cat, reason) in enumerate([("won", "产品质量优秀"), ("won", "价格合理"), ("won", "交期保障"),
                        ("lost", "价格偏高"), ("lost", "交期无法满足"), ("lost", "竞争对手品牌优势")], 1):
        db.add(CrmWinLossReason(tenant_id=TENANT_ID, type=cat, category=cat, code=f"WLR-{idx3:03d}", name=reason))

    db.flush()
    return customers


# ════════════════════════════════════════════════════════════
#  Phase 5: Orders & Production
# ════════════════════════════════════════════════════════════

def seed_orders_production(db, customers, skus, routes, processes, users, equip, prices):
    if db.query(Order).count() > 0:
        return None  # Skip if orders exist

    order_defs = [
        ("ORD-2026-001", "C-HC", "completed", 60, d(10), [
            ("SKU-GZ-BL-M", 200, D("128.00")),
            ("SKU-GZ-BL-L", 100, D("128.00")),
        ]),
        ("ORD-2026-002", "C-XD", "in_production", 30, d(-15), [
            ("SKU-FH-WH-L", 150, D("198.00")),
            ("SKU-FH-WH-XL", 50, D("208.00")),
        ]),
        ("ORD-2026-003", "C-YJ", "confirmed", 15, d(-30), [
            ("SKU-FJ-BL-M", 80, D("158.00")),
            ("SKU-FJ-BL-L", 50, D("158.00")),
        ]),
        ("ORD-2026-004", "C-HC", "draft", 5, d(-45), [
            ("SKU-GZ-GY-M", 300, D("128.00")),
        ]),
    ]

    all_orders = []
    for code, ccode, status, created_offset, due_offset, items in order_defs:
        cust = customers[ccode]
        total = sum(D(str(qty)) * price for _, qty, price in items)

        o = Order(
            code=code, customer_id=cust.id, status=status,
            due_date=due_offset,
            amount=total, confirmed_at=dt(created_offset - 2, 14) if status != "draft" else None,
            confirmed_by=users["wangjianguo"].id if status != "draft" else None,
            actual_completed_at=dt(3, 16) if status == "completed" else None,
        )
        db.add(o); db.flush()

        order_items = []
        work_orders = []
        for line_no, (sku_code, qty, unit_price) in enumerate(items, 1):
            sku = skus[sku_code]
            oi = OrderItem(
                order_id=o.id, line_no=line_no, sku_id=sku.id,
                qty=qty, unit_price=unit_price, subtotal=D(str(qty)) * unit_price,
            )
            db.add(oi); db.flush()
            order_items.append((oi, sku, qty))

            # Create work order if not draft
            if status != "draft":
                wo_status = "completed" if status == "completed" else ("in_progress" if status == "in_production" else "open")
                wo = WorkOrder(
                    order_id=o.id, order_item_id=oi.id,
                    product_id=sku.product_id, sku_id=sku.id,
                    qty=qty, status=wo_status,
                    started_at=dt(created_offset - 5, 8) if wo_status != "open" else None,
                    finished_at=dt(3, 17) if wo_status == "completed" else None,
                )
                db.add(wo); db.flush()
                work_orders.append((wo, sku, qty))

        all_orders.append((o, order_items, work_orders, status, ccode))

    # Production plan for order 2 (in production)
    ord2 = all_orders[1][0]
    plan = ProductionPlan(
        order_id=ord2.id, code="PLAN-2026-001", status="released",
        start_date=d(25), end_date=d(-10), work_days=20,
        created_by=users["wangjianguo"].id, released_by=users["wangjianguo"].id,
    )
    db.add(plan)
    db.flush()

    return all_orders


# ════════════════════════════════════════════════════════════
#  Phase 6: Tasks, Reports, Quality
# ════════════════════════════════════════════════════════════

def seed_tasks_reports_quality(db, orders_data, users, processes, prices, equip):
    if not orders_data:
        return
    if db.query(Task).count() > 0:
        return

    # Process-to-equipment mapping
    proc_equip = {
        "PROC-CUT": "EQ-CUT-01", "PROC-SEW": "EQ-SEW-01",
        "PROC-IRON": "EQ-IRON-01", "PROC-QC": None, "PROC-PKG": "EQ-PKG-01",
    }
    # Process-to-workers mapping
    proc_workers = {
        "PROC-CUT": [("lizhiqiang", "leader"), ("liuyang", "worker"), ("zhaojing", "worker")],
        "PROC-SEW": [("zhangwei", "leader"), ("sunli", "worker"), ("zhoufang", "worker"), ("wulei", "worker")],
        "PROC-IRON": [("chenming", "leader"), ("zhengpeng", "worker")],
        "PROC-QC": [("hemin", "inspector")],
        "PROC-PKG": [("chenming", "leader"), ("huangting", "worker")],
    }

    all_salary_items = []

    for order, order_items, work_orders, status, ccode in orders_data:
        if status == "draft":
            continue

        for wo, sku, qty in work_orders:
            # Get route steps for this product
            route_steps = db.query(ProcessRouteStep).join(ProcessRoute).filter(
                ProcessRoute.product_id == sku.product_id,
                ProcessRoute.is_default == True,
            ).order_by(ProcessRouteStep.seq).all()

            for step in route_steps:
                proc = processes.get(step.process.code)
                if not proc:
                    continue

                task_status = "completed" if status == "completed" else (
                    "in_progress" if proc.code in ["PROC-CUT", "PROC-SEW"] else "pending"
                )
                if status == "completed":
                    task_status = "completed"

                eq_code = proc_equip.get(proc.code)
                task = Task(
                    work_order_id=wo.id, process_id=proc.id,
                    seq=step.seq, task_code=f"T{wo.id}-{sku.code[-7:]}-{proc.code[-3:]}",
                    planned_qty=qty, status=task_status,
                    assigned_user_id=users[proc_workers[proc.code][0][0]].id,
                    equipment_id=equip[eq_code].id if eq_code and eq_code in equip else None,
                )
                db.add(task); db.flush()

                # Assignments
                for uname, _ in proc_workers[proc.code]:
                    if uname in users:
                        assign_qty = qty // len(proc_workers[proc.code])
                        ta = TaskAssignment(
                            task_id=task.id, user_id=users[uname].id,
                            assigned_qty=assign_qty, assigned_by=users["wangjianguo"].id,
                        )
                        db.add(ta); db.flush()

                        # Reports for completed/in_progress tasks
                        if task_status in ("completed", "in_progress"):
                            good_qty = assign_qty
                            bad_qty = 0
                            # Add some realistic defects
                            if proc.code == "PROC-SEW" and random.random() < 0.3:
                                bad_qty = random.randint(1, 3)
                                good_qty -= bad_qty

                            report_status = "qc_approved" if task_status == "completed" else "submitted"
                            rpt = Report(
                                task_id=task.id, report_user_id=users[uname].id,
                                good_qty=good_qty, bad_qty=bad_qty, status=report_status,
                            )
                            db.add(rpt); db.flush()

                            # Audit records
                            if report_status in ("leader_approved", "qc_approved"):
                                audit1 = ReportAudit(
                                    report_id=rpt.id, auditor_id=users[proc_workers[proc.code][0][0]].id,
                                    audit_level="leader", action="approve",
                                    created_at=dt(random.randint(1, 18), 17),
                                )
                                db.add(audit1)
                                audit2 = ReportAudit(
                                    report_id=rpt.id, auditor_id=users["hemin"].id,
                                    audit_level="qc", action="approve",
                                    created_at=dt(random.randint(1, 15), 9),
                                )
                                db.add(audit2)

                            # Salary item
                            price_key = (sku.code, proc.code)
                            unit_price = prices[price_key].unit_price if price_key in prices else D("5.00")
                            amount = unit_price * good_qty
                            si = SalaryItem(
                                report_id=rpt.id, user_id=users[uname].id,
                                sku_id=sku.id, process_id=proc.id,
                                unit_price=unit_price, good_qty=good_qty,
                                amount=amount, item_type="piece",
                                work_date=d(random.randint(1, 25)),
                                month=MONTH,
                            )
                            db.add(si)
                            all_salary_items.append((users[uname], amount, MONTH))

    db.flush()


# ════════════════════════════════════════════════════════════
#  Phase 7: Salary & Attendance
# ════════════════════════════════════════════════════════════

def seed_salary_attendance(db, users, prices):
    if db.query(SalarySlip).count() > 0:
        return

    # Generate salary slips from salary_items
    worker_usernames = ["lizhiqiang", "liuyang", "zhaojing", "zhangwei", "sunli",
                        "zhoufang", "wulei", "chenming", "zhengpeng", "huangting"]

    for uname in worker_usernames:
        if uname not in users:
            continue
        u = users[uname]
        items = db.query(SalaryItem).filter(
            SalaryItem.user_id == u.id, SalaryItem.month == MONTH
        ).all()
        if not items:
            # Generate some dummy salary items for workers without reports
            if u.salary_type == "piece":
                item_amount = D(str(random.randint(3000, 6000)))
            else:
                item_amount = D("0")
        else:
            item_amount = sum(si.amount for si in items)

        # Add some bonus
        bonus = D(str(random.choice([200, 300, 500, 0])))
        deduction = D(str(random.choice([0, 0, 50, 100])))
        hourly_amount = D("0")
        hourly_hours = D("0")
        net = item_amount + bonus - deduction

        slip = SalarySlip(
            user_id=u.id, month=MONTH,
            item_amount=item_amount, hourly_amount=hourly_amount,
            hourly_hours=hourly_hours, bonus_amount=bonus,
            deduction_amount=deduction, net_amount=net,
            total_qty=sum(si.good_qty for si in items) if items else 0,
            confirm_status=random.choice(["pending", "pending", "confirmed"]),
        )
        db.add(slip)

    # Attendance records (last 25 days)
    all_workers = ["wangjianguo", "lizhiqiang", "zhangwei", "chenming",
                   "liuyang", "zhaojing", "sunli", "zhoufang", "wulei",
                   "zhengpeng", "huangting", "hemin", "linfeng", "xuna", "yangjie"]
    for uname in all_workers:
        if uname not in users:
            continue
        u = users[uname]
        for days_ago in range(1, 26):
            work_day = d(days_ago)
            if work_day.weekday() >= 5:  # Skip weekends
                continue
            # Check in/out times with some variation
            ci_hour = random.choice([7, 7, 7, 8, 8])
            ci_min = random.randint(0, 59)
            co_hour = random.choice([17, 17, 18, 18, 18])
            co_min = random.randint(0, 59)
            ar = AttendanceRecord(
                user_id=u.id, work_date=work_day,
                check_in_at=datetime(work_day.year, work_day.month, work_day.day, ci_hour, ci_min),
                check_out_at=datetime(work_day.year, work_day.month, work_day.day, co_hour, co_min),
                check_in_ip="192.168.1.100",
                check_out_ip="192.168.1.100",
            )
            db.add(ar)

    # Shifts
    shift_defs = [
        ("SHIFT-DAY", "白班", time(8, 0), time(17, 0), 60, "day"),
        ("SHIFT-NIGHT", "夜班", time(20, 0), time(5, 0), 60, "night"),
    ]
    shifts = {}
    for code, name, start, end, rest, stype in shift_defs:
        s = Shift(code=code, name=name, start_time=start, end_time=end,
                  rest_minutes=rest, shift_type=stype, status="active")
        db.add(s); db.flush()
        shifts[code] = s

    # Shift schedules for workers (current month)
    day_shift = shifts["SHIFT-DAY"]
    for uname in ["lizhiqiang", "liuyang", "zhaojing", "zhangwei", "sunli",
                  "zhoufang", "wulei", "chenming", "zhengpeng", "huangting"]:
        if uname not in users:
            continue
        for days_ago in range(0, 26):
            work_day = d(days_ago)
            if work_day.weekday() >= 5:
                continue
            ss = ShiftSchedule(
                user_id=users[uname].id, shift_id=day_shift.id,
                work_date=work_day.strftime("%Y-%m-%d"),
            )
            db.add(ss)

    db.flush()


# ════════════════════════════════════════════════════════════
#  Phase 8: Support data
# ════════════════════════════════════════════════════════════

def seed_support(db, users, customers):
    # Notifications
    if db.query(Notification).count() == 0:
        notif_defs = [
            ("admin", "系统初始化完成", "演示数据已成功导入", "info"),
            ("wangjianguo", "新订单待确认", "ORD-2026-004 华辰有限公司新订单待审核", "warning"),
            ("wangjianguo", "生产进度提醒", "ORD-2026-002 防护服订单缝纫工序进度已达60%", "info"),
            ("hemin", "质检待审批", "ORD-2026-002 有3条报工记录待您审批", "warning"),
            ("linfeng", "CRM商机更新", "华辰2026秋季工装采购 已进入谈判阶段", "info"),
            ("linfeng", "新线索分配", "武汉光电有限公司 新线索已分配给您", "info"),
            ("lizhiqiang", "任务分配通知", "ORD-2026-002 裁剪任务已分配", "info"),
            ("zhangwei", "任务分配通知", "ORD-2026-002 缝纫任务已分配", "info"),
            ("xuna", "库存预警", "涤棉面料库存低于安全库存，请及时采购", "warning"),
            ("yangjie", "工资条待确认", f"{MONTH}月工资条已生成，请通知员工确认", "info"),
        ]
        for uname, title, content, level in notif_defs:
            if uname in users:
                n = Notification(
                    user_id=users[uname].id, title=title, content=content,
                    level=level, created_at=dt(random.randint(0, 5), 9),
                )
                db.add(n)

    # Inspection templates
    if db.query(InspectionTemplate).count() == 0:
        tmpl = InspectionTemplate(
            code="IT-SEW-01", name="缝纫工序质检标准",
            description="缝纫完成后的质量检验标准",
            process_id=db.query(Process).filter(Process.code == "PROC-QC").first().id,
        )
        db.add(tmpl); db.flush()

        items = [
            (1, "线迹平整度", "pass_fail", None, None, None, None, True),
            (2, "缝份宽度(mm)", "measure", "10", "11", "9", "mm", True),
            (3, "针距密度(针/3cm)", "measure", "12", "14", "10", "针", True),
            (4, "色差等级", "pass_fail", None, None, None, None, True),
            (5, "尺寸偏差(mm)", "measure", "0", "5", "-5", "mm", True),
            (6, "备注", "text", None, None, None, None, False),
        ]
        for seq, name, itype, std, upper, lower, unit, req in items:
            iti = InspectionTemplateItem(
                template_id=tmpl.id, seq=seq, item_name=name,
                item_type=itype, standard_value=std,
                upper_limit=upper, lower_limit=lower, unit=unit,
                is_required=req,
            )
            db.add(iti)

    # Defect codes
    if db.query(DefectCode).count() == 0:
        defects = [
            ("DEF-001", "跳线", "major"), ("DEF-002", "断线", "major"),
            ("DEF-003", "褶皱", "minor"), ("DEF-004", "色差超标", "major"),
            ("DEF-005", "尺寸超差", "critical"), ("DEF-006", "污渍", "minor"),
            ("DEF-007", "破损", "critical"), ("DEF-008", "拉链不顺", "minor"),
        ]
        for code, name, severity in defects:
            db.add(DefectCode(code=code, name=name, severity=severity))

    # Tenant settings
    if db.query(TenantSetting).count() == 0:
        settings = [
            ("company.name", "辰科工装制造有限公司"),
            ("company.address", "重庆市渝北区金开大道100号"),
            ("company.phone", "023-8888-6666"),
            ("company.logo", ""),
            ("crm.public_pool.recycle_days", "90"),
            ("salary.piece.round_mode", "floor"),
        ]
        for key, value in settings:
            db.add(TenantSetting(key=key, value=value))

    # Print templates
    if db.query(PrintTemplate).count() == 0:
        templates = [
            ("TPL-ORDER", "订单确认单", "html", "<h1>订单确认单</h1><p>订单编号: {{code}}</p>"),
            ("TPL-WO", "工单流转卡", "html", "<h1>工单流转卡</h1><p>工单号: {{code}}</p>"),
            ("TPL-SALARY", "工资条", "html", "<h1>工资条</h1><p>{{month}}月</p>"),
        ]
        for code, name, ttype, content in templates:
            db.add(PrintTemplate(code=code, name=name, template_type=ttype, content=content, is_active=True))

    # Production calendar (current month)
    if db.query(ProductionCalendarDay).count() == 0:
        first_day = TODAY.replace(day=1)
        for i in range(31):
            day = first_day + timedelta(days=i)
            if day.month != first_day.month:
                break
            is_workday = day.weekday() < 5
            db.add(ProductionCalendarDay(
                day=day, is_workday=is_workday,
                capacity_minutes=480 if is_workday else 0,
            ))

    db.flush()


if __name__ == "__main__":
    main()
