from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attendance import check_in, check_out, list_attendance_records
from app.crud.tenant_setting import get_setting, upsert_setting
from app.models.user import User
from app.schemas.attendance import AttendanceCheckInIn, AttendanceCheckOutIn, AttendanceGeofenceIn
from app.services.attendance_geofence import KEY as GEOFENCE_KEY, get_geofence_config
import json

router = APIRouter(prefix="/attendance", tags=["h5-attendance"])


def _ensure_employee(user: User) -> None:
    roles = {r.code for r in user.roles}
    if not ({"employee", "leader"} & roles):
        raise HTTPException(status_code=403, detail="无权限")


def _out(x) -> dict:
    minutes = None
    if x.check_in_at and x.check_out_at:
        minutes = int((x.check_out_at - x.check_in_at).total_seconds() // 60)
    return {
        "id": x.id,
        "work_date": x.work_date,
        "check_in_at": x.check_in_at,
        "check_out_at": x.check_out_at,
        "check_in_lat": getattr(x, "check_in_lat", None),
        "check_in_lng": getattr(x, "check_in_lng", None),
        "check_out_lat": getattr(x, "check_out_lat", None),
        "check_out_lng": getattr(x, "check_out_lng", None),
        "remark": x.remark,
        "minutes": minutes,
    }


@router.post("/check-in")
def check_in_api(
    request: Request,
    payload: AttendanceCheckInIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    ip = request.client.host if request.client else None
    body = payload or AttendanceCheckInIn()
    try:
        rec = check_in(
            db,
            user_id=user.id,
            now=datetime.now(),
            ip=ip,
            lat=body.latitude,
            lng=body.longitude,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(_out(rec))


@router.post("/check-out")
def check_out_api(
    request: Request,
    payload: AttendanceCheckOutIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    ip = request.client.host if request.client else None
    body = payload or AttendanceCheckOutIn()
    try:
        rec = check_out(
            db,
            user_id=user.id,
            now=datetime.now(),
            ip=ip,
            lat=body.latitude,
            lng=body.longitude,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(_out(rec))


@router.get("/records")
def my_records_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_employee(user)
    items = list_attendance_records(
        db,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})


@router.get("/geofence")
def geofence_public_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_employee(user)
    cfg = get_geofence_config(db)
    if not cfg:
        return ok({"enabled": False})
    return ok({"enabled": True, "lat": cfg["lat"], "lng": cfg["lng"], "radius_m": cfg["radius_m"]})
