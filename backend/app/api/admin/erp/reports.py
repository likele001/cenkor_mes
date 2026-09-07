from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_ledger import balance_sheet, trial_balance
from app.models.user import User


router = APIRouter()


@router.get("/trial-balance")
def trial_balance_api(
    period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = trial_balance(db, user.tenant_id, period)
    return ok({"period": period, "items": rows})


@router.get("/balance-sheet")
def balance_sheet_api(
    period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = balance_sheet(db, user.tenant_id, period)
    return ok(result)
