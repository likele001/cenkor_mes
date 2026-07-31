from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.services.attendance_geofence import assert_within_geofence


def get_record_by_id(db: Session, record_id: int) -> AttendanceRecord | None:
    return db.scalar(select(AttendanceRecord).where(AttendanceRecord.id == record_id))


def get_record_by_user_and_date(db: Session, user_id: int, work_date: date) -> AttendanceRecord | None:
    return db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date == work_date,
        )
    )


def check_in(
    db: Session,
    user_id: int,
    now: datetime,
    ip: str | None,
    lat: float | None = None,
    lng: float | None = None,
) -> AttendanceRecord:
    assert_within_geofence(db, lat, lng)
    wd = now.date()
    rec = get_record_by_user_and_date(db, user_id=user_id, work_date=wd)
    if rec and rec.check_in_at:
        raise ValueError("今日已打卡上班")
    if not rec:
        rec = AttendanceRecord(user_id=user_id, work_date=wd)
        db.add(rec)
        db.flush()
    rec.check_in_at = now
    rec.check_in_ip = ip
    rec.check_in_lat = lat
    rec.check_in_lng = lng
    db.flush()
    return rec


def check_out(
    db: Session,
    user_id: int,
    now: datetime,
    ip: str | None,
    lat: float | None = None,
    lng: float | None = None,
) -> AttendanceRecord:
    assert_within_geofence(db, lat, lng)
    wd = now.date()
    rec = get_record_by_user_and_date(db, user_id=user_id, work_date=wd)
    if not rec or not rec.check_in_at:
        raise ValueError("今日未打卡上班")
    if rec.check_out_at:
        raise ValueError("今日已打卡下班")
    rec.check_out_at = now
    rec.check_out_ip = ip
    rec.check_out_lat = lat
    rec.check_out_lng = lng
    db.flush()
    return rec


def list_attendance_records(
    db: Session,
    user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AttendanceRecord]:
    stmt = select(AttendanceRecord)
    if user_id is not None:
        stmt = stmt.where(AttendanceRecord.user_id == user_id)
    if date_from:
        stmt = stmt.where(AttendanceRecord.work_date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceRecord.work_date <= date_to)
    stmt = stmt.order_by(AttendanceRecord.work_date.desc(), AttendanceRecord.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_attendance_record(
    db: Session,
    rec: AttendanceRecord,
    check_in_at: datetime | None = None,
    check_out_at: datetime | None = None,
    remark: str | None = None,
) -> AttendanceRecord:
    if check_in_at is not None:
        rec.check_in_at = check_in_at
    if check_out_at is not None:
        rec.check_out_at = check_out_at
    if remark is not None:
        rec.remark = remark
    db.flush()
    return rec
