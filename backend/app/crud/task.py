from datetime import datetime

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.order import Order
from app.models.process import Process
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.models.work_order import WorkOrder


def _task_load_options():
    return (
        selectinload(Task.process),
        selectinload(Task.work_order).selectinload(WorkOrder.sku).selectinload(Sku.product),
        selectinload(Task.work_order).selectinload(WorkOrder.product),
        selectinload(Task.work_order).selectinload(WorkOrder.order).selectinload(Order.customer),
        selectinload(Task.equipment),
    )


def get_task_by_id(db: Session, task_id: int, with_refs: bool = False) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    if with_refs:
        stmt = stmt.options(*_task_load_options())
    return db.scalar(stmt)


def get_task_by_code(db: Session, task_code: str, with_refs: bool = False) -> Task | None:
    stmt = select(Task).where(Task.task_code == task_code)
    if with_refs:
        stmt = stmt.options(*_task_load_options())
    return db.scalar(stmt)


def list_tasks(
    db: Session,
    work_order_id: int | None = None,
    assigned_user_id: int | None = None,
    keyword: str | None = None,
    status: str | None = None,
    with_refs: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Task]:
    stmt = select(Task)
    if with_refs:
        stmt = stmt.options(*_task_load_options())
    if work_order_id is not None:
        stmt = stmt.where(Task.work_order_id == work_order_id)
    if assigned_user_id is not None:
        stmt = stmt.where(
            exists().where(
                TaskAssignment.task_id == Task.id,
                TaskAssignment.user_id == assigned_user_id,
            )
        )
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = (
            stmt.join(WorkOrder, WorkOrder.id == Task.work_order_id)
            .join(Order, Order.id == WorkOrder.order_id)
            .outerjoin(Customer, Customer.id == Order.customer_id)
            .outerjoin(Sku, Sku.id == WorkOrder.sku_id)
            .outerjoin(Process, Process.id == Task.process_id)
            .outerjoin(
                TaskAssignment,
                TaskAssignment.task_id == Task.id,
            )
            .outerjoin(User, User.id == TaskAssignment.user_id)
            .where(
                or_(
                    Task.task_code.like(kw),
                    Order.code.like(kw),
                    Customer.name.like(kw),
                    Customer.code.like(kw),
                    Sku.code.like(kw),
                    Sku.name.like(kw),
                    Process.name.like(kw),
                    Process.code.like(kw),
                    User.username.like(kw),
                    User.full_name.like(kw),
                )
            )
            .distinct()
        )
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def assign_task(db: Session, task: Task, assigned_user_id: int | None, dispatcher_user_id: int) -> Task:
    task.assigned_user_id = assigned_user_id
    if assigned_user_id is None:
        task.assigned_at = None
        task.assigned_by = None
    else:
        task.assigned_at = datetime.now()
        task.assigned_by = dispatcher_user_id
    db.flush()
    return task


def set_task_equipment(db: Session, task: Task, equipment_id: int | None) -> Task:
    task.equipment_id = equipment_id
    db.flush()
    return task
