"""批量添加型号及工序工价（对标 thinkmes batchAddModels）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.process import get_process_by_id, list_processes
from app.crud.process_price import batch_upsert_prices
from app.crud.process_route import get_default_route_for_product
from app.crud.sku import create_sku, get_sku_by_code
from app.models.process import Process
from app.models.sku import Sku
from app.services.code_generator import BizType, resolve_code
from app.services.display_label import process_display_name


def list_active_sku_names_for_product(db: Session, product_id: int) -> list[str]:
    rows = db.scalars(
        select(Sku.name).where(
            Sku.product_id == product_id,
            Sku.is_active.is_(True),
        )
    ).all()
    names: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def get_product_route_processes(
    db: Session,
    product_id: int,
) -> tuple[list[Process], str | None, str]:
    try:
        route = get_default_route_for_product(db, product_id)
        proc_ids = [s.process_id for s in sorted(route.steps, key=lambda x: x.seq)]
        if proc_ids:
            proc_map = {
                p.id: p
                for p in db.scalars(
                    select(Process).where(Process.id.in_(proc_ids))
                ).all()
            }
            process_rows = [proc_map[pid] for pid in proc_ids if pid in proc_map]
            if process_rows:
                return process_rows, route.name, "default_route"
    except ValueError:
        pass
    process_rows = list_processes(db, offset=0, limit=500, include_inactive=False)
    return process_rows, None, "all"


def process_rows_to_dict(process_rows: list[Process]) -> list[dict]:
    return [
        {
            "process_id": p.id,
            "process_code": p.code,
            "process_name": p.name,
            "process_display_name": process_display_name(p.name, p.code),
        }
        for p in process_rows
    ]


def batch_create_skus_with_prices(
    db: Session,
    product_id: int,
    items: list[dict],
) -> dict:
    """
    批量创建型号并写入工价。同产品下型号名称重复则跳过（与 thinkmes 一致）。
    items: [{code?, name, color?, material?, spec?, remark?, is_active?, prices: [{process_id, unit_price?, is_active?}]}]
    """
    existing_names = set(list_active_sku_names_for_product(db, product_id))
    seen_codes: set[str] = set()

    added = 0
    skipped = 0
    prices_created = 0
    prices_updated = 0
    created_items: list[dict] = []

    for raw in items:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        if name in existing_names:
            skipped += 1
            continue

        code_input = raw.get("code")
        code = resolve_code(
            db,
            biz_type=BizType.SKU,
            code=code_input,
            exists=lambda c: get_sku_by_code(db, c) is not None or c in seen_codes,
            duplicate_msg="型号编码已存在",
        )
        seen_codes.add(code)

        for price in raw.get("prices") or []:
            process_id = int(price["process_id"])
            proc = get_process_by_id(db, process_id=process_id)
            if not proc:
                raise ValueError(f"工序#{process_id} 不存在")

        sku = create_sku(
            db,
            product_id=product_id,
            code=code,
            name=name,
            color=raw.get("color"),
            material=raw.get("material"),
            spec=raw.get("spec"),
            remark=raw.get("remark"),
            is_active=bool(raw.get("is_active", True)),
        )
        existing_names.add(name)
        added += 1

        price_items = [p for p in (raw.get("prices") or []) if p.get("unit_price") not in (None, "")]
        if price_items:
            c, u = batch_upsert_prices(db, sku.id, price_items)
            prices_created += c
            prices_updated += u

        created_items.append({"id": sku.id, "code": sku.code, "name": sku.name})

    return {
        "added": added,
        "skipped": skipped,
        "prices_created": prices_created,
        "prices_updated": prices_updated,
        "items": created_items,
    }
