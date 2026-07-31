from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.production_plan import ProductionPlan


def get_plan_by_id(db: Session, plan_id: int) -> ProductionPlan | None:
    return db.scalar(select(ProductionPlan).where(ProductionPlan.id == plan_id))


def get_plan_by_code(db: Session, code: str) -> ProductionPlan | None:
    return db.scalar(select(ProductionPlan).where(ProductionPlan.code == code))


def list_plans_with_order_info(
    db: Session,
    status: str | None = None,
    order_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
):
    qty_sum_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty).label("qty"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )

    stmt = (
        select(
            ProductionPlan,
            Order.code.label("order_code"),
            Order.status.label("order_status"),
            Customer.name.label("customer_name"),
            qty_sum_sq.c.qty.label("qty"),
        )
        .join(Order, Order.id == ProductionPlan.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(
            qty_sum_sq,
            qty_sum_sq.c.order_id == Order.id,
        )
    )
    if status:
        stmt = stmt.where(ProductionPlan.status == status)
    if order_id is not None:
        stmt = stmt.where(ProductionPlan.order_id == order_id)
    if date_from is not None:
        stmt = stmt.where(ProductionPlan.start_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ProductionPlan.end_date <= date_to)
    stmt = stmt.order_by(ProductionPlan.id.desc()).offset(offset).limit(limit)
    return db.execute(stmt).all()


def get_plan_with_order_info(db: Session, plan_id: int):
    qty_sum_sq = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.qty).label("qty"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )

    stmt = (
        select(
            ProductionPlan,
            Order.code.label("order_code"),
            Order.status.label("order_status"),
            Customer.name.label("customer_name"),
            qty_sum_sq.c.qty.label("qty"),
        )
        .join(Order, Order.id == ProductionPlan.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(
            qty_sum_sq,
            qty_sum_sq.c.order_id == Order.id,
        )
        .where(ProductionPlan.id == plan_id)
    )
    return db.execute(stmt).first()


def create_plan(
    db: Session,
    order_id: int,
    code: str,
    status: str,
    start_date: date | None,
    end_date: date | None,
    work_days: int | None,
    remark: str | None,
    created_by: int | None,
) -> ProductionPlan:
    plan = ProductionPlan(
        order_id=order_id,
        code=code,
        status=status,
        start_date=start_date,
        end_date=end_date,
        work_days=work_days,
        remark=remark,
        created_by=created_by,
    )
    db.add(plan)
    db.flush()
    return plan


def update_plan(
    db: Session,
    plan: ProductionPlan,
    order_id: int | None = None,
    code: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    work_days: int | None = None,
    remark: str | None = None,
) -> ProductionPlan:
    if order_id is not None:
        plan.order_id = order_id
    if code is not None:
        plan.code = code
    if status is not None:
        plan.status = status
    if start_date is not None:
        plan.start_date = start_date
    if end_date is not None:
        plan.end_date = end_date
    if work_days is not None:
        plan.work_days = work_days
    if remark is not None:
        plan.remark = remark
    db.flush()
    return plan


def plan_is_released(plan: ProductionPlan) -> bool:
    return plan.status in ("in_progress", "done") or plan.released_at is not None


def ensure_plan_released_for_dispatch(
    db: Session,
    *,
    plan: ProductionPlan,
    releaser_user_id: int,
    auto_release: bool,
    allow_shortage: bool = False,
) -> dict | None:
    if plan.status != "planned":
        return None
    if not auto_release:
        raise ValueError(
            "生产计划尚未「确认下发」。请在【生产计划】列表点击「确认下发」，"
            "或点「智能排产 → 采纳并执行」（将自动尝试下发）。"
        )
    return release_plan(
        db,
        plan=plan,
        releaser_user_id=releaser_user_id,
        allow_shortage=allow_shortage,
    )


def _count_order_tasks(db: Session, order_id: int) -> tuple[int, int]:
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    wo_count = db.scalar(
        select(func.count(WorkOrder.id)).where(WorkOrder.order_id == order_id)
    )
    task_count = db.scalar(
        select(func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .where(WorkOrder.order_id == order_id)
    )
    return int(wo_count or 0), int(task_count or 0)


def release_plan(
    db: Session,
    *,
    plan: ProductionPlan,
    releaser_user_id: int,
    allow_shortage: bool = False,
) -> dict:
    from app.crud.order import create_work_orders_for_order, get_order_by_id, order_has_work_orders
    from app.crud.plan_kitting import calc_order_kitting_shortages

    if plan.status != "planned":
        raise ValueError("仅「计划」状态的生产计划可确认下发")

    order = get_order_by_id(db, order_id=plan.order_id, with_items=True)
    if not order:
        raise ValueError("关联订单不存在")

    if order_has_work_orders(db, order.id):
        plan.status = "in_progress"
        if not plan.released_at:
            plan.released_at = datetime.now()
            plan.released_by = releaser_user_id
        if order.status == "confirmed":
            order.status = "producing"
        db.flush()
        wo_count, task_count = _count_order_tasks(db, order.id)
        return {
            "plan_id": plan.id,
            "order_id": order.id,
            "order_status": order.status,
            "synced": True,
            "work_order_count": wo_count,
            "task_count": task_count,
        }

    if order.status == "pending_confirm":
        raise ValueError(
            f"订单 {order.code or order.id} 尚未审核，请打开【订单管理】对该订单点击「审核通过」后再下发"
        )
    if order.status == "draft":
        raise ValueError(f"订单 {order.code or order.id} 仍为草稿，请先提交并审核通过")
    if order.status not in ("confirmed", "producing"):
        raise ValueError(f"订单 {order.code or order.id} 当前状态为「{order.status}」，无法下发投产")

    if not allow_shortage:
        shortages = calc_order_kitting_shortages(db, order)
        if shortages:
            names = "、".join(s["material_name"] for s in shortages[:5])
            extra = f" 等{len(shortages)}项" if len(shortages) > 5 else ""
            raise ValueError(f"物料未齐套：{names}{extra}，请先采购或在确认下发时勾选「允许缺料」")

    work_orders = create_work_orders_for_order(db, order=order)
    plan.status = "in_progress"
    plan.released_at = datetime.now()
    plan.released_by = releaser_user_id
    order.status = "producing"
    db.flush()
    return {
        "plan_id": plan.id,
        "order_id": order.id,
        "order_status": order.status,
        "work_order_count": len(work_orders),
        "task_count": sum(len(wo.tasks) for wo in work_orders),
    }
