"""计时工资核心逻辑：工时计算、每日生成、台账查询"""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from decimal import Decimal
from typing import Sequence

from sqlalchemy import Date, and_, func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.salary import SalaryItem
from app.models.shift import Shift, ShiftSchedule
from app.models.user import User


def calc_daily_hours(
    check_in_at: datetime | None,
    check_out_at: datetime | None,
    shift: Shift | None = None,
) -> tuple[Decimal, bool]:
    """计算某天工时（小时），返回 (work_hours, is_absent)

    优先级：
    1. 有打卡 → (check_out - check_in) 直接算，不截断
    2. 无打卡但有排班 → shift 标准时长
    3. 无打卡无排班 → 标记为缺卡
    """
    if check_in_at and check_out_at:
        delta = check_out_at - check_in_at
        hours = delta.total_seconds() / 3600
        return (Decimal(str(round(max(hours, 0), 2))), False)

    if shift:
        start = shift.start_time
        end = shift.end_time
        s = timedelta(hours=start.hour, minutes=start.minute, seconds=start.second)
        e = timedelta(hours=end.hour, minutes=end.minute, seconds=end.second)
        if e <= s:
            e += timedelta(days=1)
        total = (e - s).total_seconds() / 3600
        rest = (shift.rest_minutes or 0) / 60
        hours = max(total - rest, 0)
        return (Decimal(str(round(hours, 2))), False)

    return (Decimal("0"), True)


def _get_or_create_time_item(
    db: Session,
    user_id: int,
    work_date: date,
    month: str,
    work_hours: Decimal,
    hourly_rate: Decimal,
    item_type: str,
) -> SalaryItem:
    """Upsert 当天的计时工资记录"""
    existing = db.scalar(
        select(SalaryItem).where(
            SalaryItem.user_id == user_id,
            SalaryItem.work_date == work_date,
            SalaryItem.item_type.in_(["hourly", "absent"]),
        )
    )
    amount = work_hours * hourly_rate
    if existing:
        existing.work_hours = work_hours
        existing.amount = amount
        existing.item_type = item_type
        existing.month = month
        db.flush()
        return existing

    item = SalaryItem(
        user_id=user_id,
        sku_id=None,
        process_id=None,
        unit_price=hourly_rate,
        good_qty=0,
        amount=amount,
        item_type=item_type,
        work_hours=work_hours,
        work_date=work_date,
        month=month,
    )
    db.add(item)
    db.flush()
    return item


def generate_time_salary_items_for_user(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
) -> list[SalaryItem]:
    """为指定员工生成指定日期范围的计时工资记录"""
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        return []
    if user.salary_type not in ("hourly", "mixed"):
        return []

    hourly_rate = user.hourly_rate or Decimal("0")
    items: list[SalaryItem] = []
    current = date_from
    while current <= date_to:
        month = current.strftime("%Y-%m")

        attendance = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.work_date == current,
            )
        )

        shift_schedule = db.scalar(
            select(ShiftSchedule).where(
                ShiftSchedule.user_id == user_id,
                ShiftSchedule.work_date == current.isoformat(),
            )
        )
        shift = None
        if shift_schedule:
            shift = db.get(Shift, shift_schedule.shift_id)

        check_in = attendance.check_in_at if attendance else None
        check_out = attendance.check_out_at if attendance else None
        work_hours, is_absent = calc_daily_hours(check_in, check_out, shift)

        item_type = "absent" if is_absent else "hourly"
        item = _get_or_create_time_item(
            db, user_id, current, month, work_hours, hourly_rate, item_type
        )
        items.append(item)
        current += timedelta(days=1)

    db.flush()
    return items


def generate_all_time_salary_items_for_tenant(
    db: Session,
    target_date: date | None = None,
) -> int:
    """为租户下所有 hourly/mixed 员工生成指定日期的计时工资"""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    users = db.scalars(
        select(User).where(
            User.is_active.is_(True),
            User.salary_type.in_(["hourly", "mixed"]),
        )
    ).all()

    total = 0
    for u in users:
        items = generate_time_salary_items_for_user(db, u.id, target_date, target_date)
        total += len(items)
    return total


def list_hourly_items(
    db: Session,
    month: str | None = None,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[Sequence[SalaryItem], int]:
    """查询计时工资明细"""
    stmt = select(SalaryItem).where(
        SalaryItem.item_type.in_(["hourly", "absent"]),
    )
    if month:
        stmt = stmt.where(SalaryItem.month == month)
    if user_id is not None:
        stmt = stmt.where(SalaryItem.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(SalaryItem.work_date.desc(), SalaryItem.user_id).offset(offset).limit(limit)
    items = db.scalars(stmt).all()
    return items, total


def get_hourly_summary(
    db: Session,
    month: str | None = None,
    user_id: int | None = None,
) -> dict:
    """计时工资汇总：总工时、总金额"""
    stmt = select(
        func.coalesce(func.sum(SalaryItem.work_hours), 0).label("total_hours"),
        func.coalesce(func.sum(SalaryItem.amount), 0).label("total_amount"),
    ).where(
        SalaryItem.item_type == "hourly",
    )
    if month:
        stmt = stmt.where(SalaryItem.month == month)
    if user_id is not None:
        stmt = stmt.where(SalaryItem.user_id == user_id)

    row = db.execute(stmt).one()
    return {
        "total_hours": float(row.total_hours),
        "total_amount": float(row.total_amount),
    }
