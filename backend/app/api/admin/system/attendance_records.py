from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attendance import get_record_by_id, list_attendance_records, update_attendance_record
from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.schemas.attendance import AttendanceGeofenceIn, AttendanceRecordCreateIn, AttendanceRecordUpdateIn
from app.services.attendance_geofence import KEY as GEOFENCE_KEY, get_geofence_config
from app.crud.tenant_setting import upsert_setting
import json


router = APIRouter(dependencies=[Depends(require_permissions(["attendance.manage"]))])


def _out(x: AttendanceRecord, u: User | None = None) -> dict:
    minutes = None
    if x.check_in_at and x.check_out_at:
        minutes = int((x.check_out_at - x.check_in_at).total_seconds() // 60)
    return {
        "id": x.id,
        "user_id": x.user_id,
        "user_name": u.full_name if u else None,
        "work_date": x.work_date,
        "check_in_at": x.check_in_at,
        "check_out_at": x.check_out_at,
        "check_in_lat": getattr(x, "check_in_lat", None),
        "check_in_lng": getattr(x, "check_in_lng", None),
        "check_out_lat": getattr(x, "check_out_lat", None),
        "check_out_lng": getattr(x, "check_out_lng", None),
        "remark": x.remark,
        "minutes": minutes,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    user_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_attendance_records(
        db,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    uids = {x.user_id for x in items}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(uids))).all()} if uids else {}
    return ok({"items": [_out(x, users.get(x.user_id)) for x in items]})


@router.post("")
def create_api(
    payload: AttendanceRecordCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == payload.user_id,
            AttendanceRecord.work_date == payload.work_date,
        )
    )
    if exists:
        raise HTTPException(status_code=400, detail="该员工当天已有考勤记录")
    rec = AttendanceRecord(
        user_id=payload.user_id,
        work_date=payload.work_date,
        check_in_at=payload.check_in_at,
        check_out_at=payload.check_out_at,
        remark=payload.remark,
    )
    db.add(rec)
    db.flush()
    write_op_log(
        db,
        request,
        user,
        module="system.attendance",
        action="create",
        object_type="attendance_record",
        object_id=rec.id,
        detail=f"user_id={rec.user_id}|work_date={rec.work_date}",
    )
    db.commit()
    return ok(_out(rec))


@router.put("/{record_id}")
def update_api(
    record_id: int,
    payload: AttendanceRecordUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rec = get_record_by_id(db, record_id=record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="考勤记录不存在")
    update_attendance_record(db, rec, check_in_at=payload.check_in_at, check_out_at=payload.check_out_at, remark=payload.remark)
    write_op_log(
        db,
        request,
        user,
        module="system.attendance",
        action="update",
        object_type="attendance_record",
        object_id=rec.id,
        detail=f"user_id={rec.user_id}|work_date={rec.work_date}",
    )
    db.commit()
    return ok(_out(rec))


@router.get("/geofence")
def get_geofence_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = get_geofence_config(db)
    if not cfg:
        return ok({"enabled": False, "lat": None, "lng": None, "radius_m": 200})
    return ok({"enabled": True, **cfg})


@router.put("/geofence")
def set_geofence_api(
    payload: AttendanceGeofenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    value = json.dumps(
        {
            "enabled": payload.enabled,
            "lat": payload.lat,
            "lng": payload.lng,
            "radius_m": payload.radius_m or 200,
        },
        ensure_ascii=False,
    )
    upsert_setting(db, key=GEOFENCE_KEY, value=value)
    db.commit()
    return ok({"saved": True})
