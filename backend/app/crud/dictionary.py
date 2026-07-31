from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictionary import DictType, DictItem


def get_dict_type_by_id(db: Session, dict_type_id: int) -> DictType | None:
    return db.scalar(
        select(DictType).where(DictType.id == dict_type_id)
    )


def get_dict_type_by_code(db: Session, code: str) -> DictType | None:
    return db.scalar(
        select(DictType).where(DictType.code == code)
    )


def list_dict_types(db: Session) -> list[DictType]:
    return db.scalars(
        select(DictType)
        .order_by(DictType.id)
    ).all()


def create_dict_type(
    db: Session,
    code: str,
    name: str,
) -> DictType:
    dt = DictType(code=code, name=name)
    db.add(dt)
    db.flush()
    return dt


def update_dict_type(
    db: Session,
    item: DictType,
    code: str | None = None,
    name: str | None = None,
) -> DictType:
    if code is not None:
        item.code = code
    if name is not None:
        item.name = name
    db.flush()
    return item


def delete_dict_type(db: Session, item: DictType) -> None:
    db.delete(item)
    db.flush()


def list_dict_items(db: Session, dict_type_id: int) -> list[DictItem]:
    return db.scalars(
        select(DictItem)
        .where(DictItem.dict_type_id == dict_type_id)
        .order_by(DictItem.sort_order, DictItem.id)
    ).all()


def get_dict_item_by_id(db: Session, dict_type_id: int, item_id: int) -> DictItem | None:
    return db.scalar(
        select(DictItem).where(
            DictItem.dict_type_id == dict_type_id,
            DictItem.id == item_id,
        )
    )


def create_dict_item(
    db: Session,
    dict_type_id: int,
    label: str,
    value: str,
    sort_order: int = 0,
) -> DictItem:
    di = DictItem(
        dict_type_id=dict_type_id,
        label=label,
        value=value,
        sort_order=sort_order,
    )
    db.add(di)
    db.flush()
    return di


def update_dict_item(
    db: Session,
    item: DictItem,
    label: str | None = None,
    value: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> DictItem:
    if label is not None:
        item.label = label
    if value is not None:
        item.value = value
    if sort_order is not None:
        item.sort_order = sort_order
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item


def delete_dict_item(db: Session, item: DictItem) -> None:
    db.delete(item)
    db.flush()
