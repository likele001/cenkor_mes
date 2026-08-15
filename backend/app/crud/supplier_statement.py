from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.material import Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.supplier_statement import SupplierStatement, SupplierStatementItem
from app.models.finance_ledger import FinanceLedger


def get_supplier_statement_by_id(db: Session, statement_id: int) -> SupplierStatement | None:
    return db.scalar(
        select(SupplierStatement)
        .where(SupplierStatement.id == statement_id)
        .options(
            selectinload(SupplierStatement.supplier),
            selectinload(SupplierStatement.items).selectinload(SupplierStatementItem.purchase_order),
        )
    )


def get_supplier_statement_by_code(db: Session, code: str) -> SupplierStatement | None:
    return db.scalar(select(SupplierStatement).where(SupplierStatement.code == code))


def list_supplier_statements(
    db: Session,
    supplier_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[SupplierStatement]:
    stmt = select(SupplierStatement).options(selectinload(SupplierStatement.supplier))
    if supplier_id is not None:
        stmt = stmt.where(SupplierStatement.supplier_id == supplier_id)
    if status:
        stmt = stmt.where(SupplierStatement.status == status)
    stmt = stmt.order_by(SupplierStatement.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_supplier_statement(
    db: Session,
    supplier_id: int,
    code: str,
    order_amounts: list[tuple[int, Decimal]],
    period_start: date | None = None,
    period_end: date | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> SupplierStatement:
    total = sum(amt for _, amt in order_amounts)
    stmt = SupplierStatement(
        supplier_id=supplier_id,
        code=code,
        period_start=period_start,
        period_end=period_end,
        total_amount=total,
        remark=remark,
        status="draft",
        created_by=created_by,
    )
    stmt.items = [
        SupplierStatementItem(purchase_order_id=oid, amount=amt)
        for oid, amt in order_amounts
    ]
    db.add(stmt)
    db.flush()
    return stmt


def update_supplier_statement_status(db: Session, stmt: SupplierStatement, new_status: str) -> SupplierStatement:
    stmt.status = new_status
    db.flush()
    return stmt


def calc_purchase_order_amount(db: Session, order: PurchaseOrder) -> Decimal:
    """采购单金额 = 已收数量 * 单价（未收货不计应付）"""
    if order.status in {"draft", "canceled"}:
        raise ValueError(f"采购单 {order.code} 未确认，不能对账")
    total = Decimal("0")
    for it in (order.items or []):
        if it.received_qty <= 0:
            continue
        price = it.unit_price
        if price is None:
            raise ValueError(f"采购单 {order.code} 明细缺少单价")
        total += Decimal(str(price)) * int(it.received_qty)
    return total


def get_supplier_payables(db: Session) -> list[dict]:
    """供应商应付汇总：应付总额（已确认对账） / 已付 / 未付"""
    rows = db.execute(
        select(
            Supplier.id,
            Supplier.code,
            Supplier.name,
            func.coalesce(func.sum(SupplierStatement.total_amount), 0).label("total_amount"),
        )
        .select_from(SupplierStatement)
        .join(Supplier, Supplier.id == SupplierStatement.supplier_id)
        .where(SupplierStatement.status.in_(["confirmed", "paid"]))
        .group_by(Supplier.id, Supplier.code, Supplier.name)
        .order_by(func.sum(SupplierStatement.total_amount).desc())
    ).all()

    paid_rows = db.execute(
        select(
            FinanceLedger.party_id,
            func.coalesce(func.sum(FinanceLedger.amount), 0).label("paid_amount"),
        )
        .where(
            FinanceLedger.party_type == "supplier",
            FinanceLedger.direction == "out",
            FinanceLedger.category == "payment",
        )
        .group_by(FinanceLedger.party_id)
    ).all()
    paid_map = {int(pid): Decimal(str(amt)) for pid, amt in paid_rows}

    result = []
    for r in rows:
        total = Decimal(str(r.total_amount))
        paid = paid_map.get(int(r.id), Decimal("0"))
        result.append({
            "supplier_id": int(r.id),
            "supplier_code": r.code,
            "supplier_name": r.name,
            "total_payable": float(total),
            "paid_amount": float(paid),
            "unpaid_amount": float(total - paid),
        })
    return result
