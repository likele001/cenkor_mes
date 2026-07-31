from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shift import Shift, ShiftSchedule


def get_shift_by_id(db: Session, shift_id: int) -> Shift | None:
    return db.scalar(select(Shift).where(Shift.id == shift_id))


def get_shift_by_code(db: Session, code: str) -> Shift | None:
    return db.scalar(select(Shift).where(Shift.code == code))


def list_shifts(
    db: Session,
    status: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[Shift]:
    stmt = select(Shift)
    if status:
        stmt = stmt.where(Shift.status == status)
    stmt = stmt.order_by(Shift.id).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_shift(
    db: Session,
    code: str,
    name: str,
    start_time: time,
    end_time: time,
    rest_minutes: int = 0,
    shift_type: str = "day",
    remark: str | None = None,
) -> Shift:
    item = Shift(
        code=code,
        name=name,
        start_time=start_time,
        end_time=end_time,
        rest_minutes=rest_minutes,
        shift_type=shift_type,
        remark=remark,
    )
    db.add(item)
    db.flush()
    return item


def update_shift(
    db: Session,
    item: Shift,
    code: str | None = None,
    name: str | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    rest_minutes: int | None = None,
    shift_type: str | None = None,
    status: str | None = None,
    remark: str | None = None,
) -> Shift:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    if start_time is not None:
        item.start_time = start_time
    if end_time is not None:
        item.end_time = end_time
    if rest_minutes is not None:
        item.rest_minutes = rest_minutes
    if shift_type is not None:
        item.shift_type = shift_type
    if status is not None:
        item.status = status
    if remark is not None:
        item.remark = remark
    db.flush()
    return item


def delete_shift(db: Session, item: Shift) -> None:
    db.delete(item)
    db.flush()


def get_shift_schedule_by_id(db: Session, schedule_id: int) -> ShiftSchedule | None:
    return db.scalar(select(ShiftSchedule).where(ShiftSchedule.id == schedule_id))


def list_shift_schedules(
    db: Session,
    user_id: int | None = None,
    work_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[ShiftSchedule]:
    stmt = select(ShiftSchedule)
    if user_id is not None:
        stmt = stmt.where(ShiftSchedule.user_id == user_id)
    if work_date:
        stmt = stmt.where(ShiftSchedule.work_date == work_date)
    if start_date:
        stmt = stmt.where(ShiftSchedule.work_date >= start_date)
    if end_date:
        stmt = stmt.where(ShiftSchedule.work_date <= end_date)
    stmt = stmt.order_by(ShiftSchedule.work_date, ShiftSchedule.user_id).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_shift_schedule(
    db: Session,
    user_id: int,
    shift_id: int,
    work_date: str,
    remark: str | None = None,
) -> ShiftSchedule:
    item = ShiftSchedule(
        user_id=user_id,
        shift_id=shift_id,
        work_date=work_date,
        remark=remark,
    )
    db.add(item)
    db.flush()
    return item


def batch_create_shift_schedules(
    db: Session,
    user_ids: list[int],
    shift_id: int,
    start_date: str,
    end_date: str,
) -> list[ShiftSchedule]:
    from datetime import date, timedelta

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    created = []
    current = start
    while current <= end:
        wd = current.isoformat()
        for uid in user_ids:
            existing = db.scalar(
                select(ShiftSchedule).where(
                    ShiftSchedule.user_id == uid,
                    ShiftSchedule.work_date == wd,
                )
            )
            if existing:
                existing.shift_id = shift_id
                created.append(existing)
            else:
                item = ShiftSchedule(
                    user_id=uid,
                    shift_id=shift_id,
                    work_date=wd,
                )
                db.add(item)
                created.append(item)
        current += timedelta(days=1)
    db.flush()
    return created


def delete_shift_schedule(db: Session, item: ShiftSchedule) -> None:
    db.delete(item)
    db.flush()
