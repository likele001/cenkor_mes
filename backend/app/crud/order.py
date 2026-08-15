from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.crud.process_route import get_default_route_for_product
from app.crud.sku import get_sku_by_id
from app.models.order import Order, OrderItem
from app.models.production_plan import ProductionPlan
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.work_order import WorkOrder

PLAN_ACTIVE_STATUSES = ("planned", "in_progress")
PRODUCTION_LOCK_PLAN_STATUSES = ("in_progress", "done")


def _next_task_seq(db: Session) -> int:
    """取现有任务编号中最大的数字序号 +1，避免与已存在编号冲突。

    原实现用 MAX(Task.id)+1：删除任务后 id 回落会导致编号复用并撞唯一约束，
    改为基于 task_code 的 TK 数字后缀计算（常规无删除时与 MAX(id) 等价）。
    """
    max_seq = 0
    for code in db.scalars(select(Task.task_code)).all():
        if code and code.startswith("TK") and code[2:].isdigit():
            n = int(code[2:])
            if n > max_seq:
                max_seq = n
    from sqlalchemy import func as sa_func
    max_id = db.scalar(select(sa_func.max(Task.id))) or 0
    return max(max_seq, max_id) + 1


def _make_task_code(seq: int) -> str:
    return f"TK{seq:06d}"


def get_order_by_id(db: Session, order_id: int, with_items: bool = False) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.customer), selectinload(Order.opportunity))
    )
    if with_items:
        stmt = stmt.options(selectinload(Order.items).selectinload(OrderItem.sku).selectinload(Sku.product))
    return db.scalar(stmt)


def get_order_by_code(db: Session, code: str) -> Order | None:
    return db.scalar(select(Order).where(Order.code == code))


def list_orders(
    db: Session,
    keyword: str | None = None,
    customer_id: int | None = None,
    opportunity_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Order]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.opportunity),
            selectinload(Order.items).selectinload(OrderItem.sku).selectinload(Sku.product),
        )
    )
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Order.code.like(kw), Order.remark.like(kw)))
    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    if opportunity_id is not None:
        stmt = stmt.where(Order.opportunity_id == opportunity_id)
    if status:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def delete_order(db: Session, order_id: int) -> None:
    order = get_order_by_id(db, order_id=order_id, with_items=False)
    if not order:
        raise ValueError("订单不存在")
    if order.status != "draft":
        raise ValueError("仅草稿状态订单可删除")
    if order_has_work_orders(db, order_id):
        raise ValueError("订单已存在工单，不可删除")
    plan_n = db.scalar(
        select(func.count(ProductionPlan.id)).where(
            ProductionPlan.order_id == order_id,
        )
    )
    if int(plan_n or 0) > 0:
        raise ValueError("订单已关联生产计划，不可删除")
    db.delete(order)
    db.flush()


def create_order(
    db: Session,
    customer_id: int,
    code: str,
    due_date,
    remark: str | None,
    items: list[tuple[int, int, int, str | None]],
    opportunity_id: int | None = None,
) -> Order:
    order = Order(
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        code=code,
        due_date=due_date,
        remark=remark,
        status="draft",
    )
    order.items = [
        OrderItem(line_no=line_no, sku_id=sku_id, qty=qty, remark=item_remark)
        for line_no, sku_id, qty, item_remark in items
    ]
    db.add(order)
    db.flush()
    return order


def update_order(
    db: Session,
    order: Order,
    customer_id: int | None = None,
    code: str | None = None,
    due_date=None,
    remark: str | None = None,
    status: str | None = None,
) -> Order:
    if customer_id is not None:
        order.customer_id = customer_id
    if code is not None:
        order.code = code
    if due_date is not None:
        order.due_date = due_date
    if remark is not None:
        order.remark = remark
    if status is not None:
        order.status = status
    db.flush()
    return order


def order_has_active_production_plan(db: Session, order_id: int) -> bool:
    n = db.scalar(
        select(func.count(ProductionPlan.id)).where(
            ProductionPlan.order_id == order_id,
            ProductionPlan.status.in_(PLAN_ACTIVE_STATUSES),
        )
    )
    return int(n or 0) > 0


def order_has_work_orders(db: Session, order_id: int) -> bool:
    n = db.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.order_id == order_id,
        )
    )
    return int(n or 0) > 0


def order_is_production_locked(db: Session, order_id: int) -> bool:
    if order_has_work_orders(db, order_id):
        return True
    n = db.scalar(
        select(func.count(ProductionPlan.id)).where(
            ProductionPlan.order_id == order_id,
            ProductionPlan.status.in_(PRODUCTION_LOCK_PLAN_STATUSES),
        )
    )
    return int(n or 0) > 0


def order_item_has_dispatched_task(db: Session, order_item_id: int) -> bool:
    n = db.scalar(
        select(func.count(TaskAssignment.id))
        .select_from(TaskAssignment)
        .join(Task, Task.id == TaskAssignment.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(
            WorkOrder.order_item_id == order_item_id,
        )
    )
    return int(n or 0) > 0


def get_order_item_lock_info(db: Session, order: Order, item: OrderItem) -> dict:
    if order.status == "draft":
        return {"locked": False, "lock_reason": None}
    if order_item_has_dispatched_task(db, item.id):
        return {"locked": True, "lock_reason": "该行已有派工"}
    return {"locked": False, "lock_reason": None}


def _validate_sku(db: Session, sku_id: int) -> Sku:
    from app.models.product import Product
    from app.services.sku_scope import is_finished_product_sku, is_material_product

    sku = get_sku_by_id(db, sku_id=sku_id)
    if not sku:
        raise ValueError("产品型号不存在")
    if not sku.is_active:
        raise ValueError("产品型号已停用")
    product = db.get(Product, sku.product_id)
    if not is_finished_product_sku(sku, product):
        raise ValueError("不能选择原材料作为订单型号，请选择成品型号")
    if product and is_material_product(product):
        raise ValueError("不能选择原材料产品，请选择成品")
    return sku


def _create_work_order_and_tasks(
    db: Session,
    order: Order,
    item: OrderItem,
    sku: Sku,
    next_seq: int,
) -> tuple[WorkOrder, int]:
    route = get_default_route_for_product(db, sku.product_id)
    wo = WorkOrder(
        order_id=order.id,
        order_item_id=item.id,
        product_id=sku.product_id,
        sku_id=sku.id,
        qty=item.qty,
        status="open",
    )
    tasks = []
    for step in route.steps:
        tasks.append(
            Task(
                task_code=_make_task_code(next_seq),
                seq=step.seq,
                process_id=step.process_id,
                planned_qty=item.qty,
                status="pending",
            )
        )
        next_seq += 1
    wo.tasks = tasks
    db.add(wo)
    db.flush()
    return wo, next_seq


def _sync_work_order_qty_from_item(db: Session, item: OrderItem) -> None:
    wo = db.scalar(
        select(WorkOrder).where(WorkOrder.order_item_id == item.id)
    )
    if not wo:
        return
    wo.qty = item.qty
    for t in db.scalars(select(Task).where(Task.work_order_id == wo.id)).all():
        t.planned_qty = item.qty
    db.flush()


def _replace_draft_items(
    db: Session,
    order: Order,
    items: list[tuple[int | None, int, int, int, str | None]],
) -> None:
    for old in list(order.items):
        db.delete(old)
    db.flush()
    order.items = [
        OrderItem(
            line_no=line_no,
            sku_id=sku_id,
            qty=qty,
            remark=remark,
        )
        for _id, line_no, sku_id, qty, remark in items
    ]
    db.flush()


def update_order_items(
    db: Session,
    order: Order,
    items: list[tuple[int | None, int, int, int, str | None]],
) -> None:
    if not items:
        raise ValueError("订单至少保留一条明细")

    seen_line: set[int] = set()
    for _id, line_no, _sku_id, _qty, _remark in items:
        if line_no in seen_line:
            raise ValueError("订单明细行号重复")
        seen_line.add(line_no)

    if order.status == "draft":
        for _id, line_no, sku_id, qty, _remark in items:
            _validate_sku(db, sku_id)
        _replace_draft_items(db, order, items)
        return

    if order.status not in ("confirmed", "producing"):
        raise ValueError("当前订单状态不允许修改明细")

    production_locked = order_is_production_locked(db, order.id)
    existing_map = {int(i.id): i for i in order.items}
    payload_ids = {int(i[0]) for i in items if i[0] is not None}

    for ex in existing_map.values():
        if ex.id not in payload_ids:
            lock = get_order_item_lock_info(db, order, ex)
            if lock["locked"]:
                raise ValueError(f"第{ex.line_no}行{lock['lock_reason']}，不可删除")
            db.delete(ex)
    db.flush()

    next_seq = _next_task_seq(db)

    for row_id, line_no, sku_id, qty, remark in items:
        sku = _validate_sku(db, sku_id)
        if row_id is None:
            if production_locked:
                raise ValueError("订单已下发投产，不可新增明细")
            new_item = OrderItem(
                order_id=order.id,
                line_no=line_no,
                sku_id=sku_id,
                qty=qty,
                remark=remark,
            )
            db.add(new_item)
            db.flush()
            if order_has_work_orders(db, order.id):
                _, next_seq = _create_work_order_and_tasks(db, order, new_item, sku, next_seq)
            continue

        ex = existing_map.get(int(row_id))
        if not ex:
            raise ValueError("订单明细不存在")
        lock = get_order_item_lock_info(db, order, ex)
        if lock["locked"]:
            if ex.qty != qty or ex.sku_id != sku_id or (ex.remark or "") != (remark or "") or ex.line_no != line_no:
                raise ValueError(f"第{ex.line_no}行{lock['lock_reason']}，不可修改")
            continue
        if ex.sku_id != sku_id:
            raise ValueError(f"第{ex.line_no}行已确认，不可更换型号")
        ex.line_no = line_no
        ex.qty = qty
        ex.remark = remark
        _sync_work_order_qty_from_item(db, ex)

    db.flush()


def submit_order_for_review(db: Session, order: Order) -> Order:
    if order.status not in ("draft",):
        raise ValueError("当前状态不可提交审核")
    order.status = "pending_confirm"
    db.flush()
    return order


def reject_order(db: Session, order: Order, reason: str) -> Order:
    if order.status != "pending_confirm":
        raise ValueError("仅待审核订单可驳回")
    order.status = "draft"
    note = (order.remark or "").strip()
    order.remark = f"{note}\n[驳回]{reason}".strip() if note else f"[驳回]{reason}"
    db.flush()
    return order


def confirm_order(db: Session, order: Order, confirmer_user_id: int) -> Order:
    if order.status not in ("draft", "pending_confirm"):
        raise ValueError("订单状态不允许确认")
    loaded = get_order_by_id(db, order_id=order.id, with_items=True)
    if not loaded or not loaded.items:
        raise ValueError("订单无明细，无法审核")
    order.status = "confirmed"
    order.confirmed_at = datetime.now()
    order.confirmed_by = confirmer_user_id
    db.flush()
    return order


def create_work_orders_for_order(db: Session, order: Order) -> list[WorkOrder]:
    if order.status not in ("confirmed", "producing"):
        raise ValueError("订单状态不允许生成工单")
    loaded = get_order_by_id(db, order_id=order.id, with_items=True)
    if not loaded:
        raise ValueError("订单不存在")
    if order_has_work_orders(db, order.id):
        raise ValueError("订单已存在工单")

    next_seq = _next_task_seq(db)
    work_orders: list[WorkOrder] = []
    for item in loaded.items:
        sku: Sku | None = item.sku
        if not sku:
            raise ValueError("订单明细产品型号不存在")
        wo, next_seq = _create_work_order_and_tasks(db, loaded, item, sku, next_seq)
        work_orders.append(wo)
    return work_orders
