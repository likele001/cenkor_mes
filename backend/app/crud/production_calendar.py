from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.production_calendar import ProductionCalendarDay


def get_calendar_day(db: Session, day: date) -> ProductionCalendarDay | None:
    return db.scalar(select(ProductionCalendarDay).where(ProductionCalendarDay.day == day))


def list_calendar_days(db: Session, date_from: date, date_to: date) -> list[ProductionCalendarDay]:
    stmt = (
        select(ProductionCalendarDay)
        .where(ProductionCalendarDay.day >= date_from, ProductionCalendarDay.day <= date_to)
        .order_by(ProductionCalendarDay.day.asc())
    )
    return db.scalars(stmt).all()


def upsert_calendar_day(
    db: Session,
    day: date,
    *,
    is_workday: bool,
    capacity_minutes: int | None,
    remark: str | None,
) -> ProductionCalendarDay:
    it = get_calendar_day(db, day=day)
    if it:
        it.is_workday = bool(is_workday)
        it.capacity_minutes = capacity_minutes
        it.remark = remark
        db.flush()
        return it
    it = ProductionCalendarDay(
        day=day,
        is_workday=bool(is_workday),
        capacity_minutes=capacity_minutes,
        remark=remark,
    )
    db.add(it)
    db.flush()
    return it


def delete_calendar_day(db: Session, day: date) -> bool:
    it = get_calendar_day(db, day=day)
    if not it:
        return False
    db.delete(it)
    db.flush()
    return True
