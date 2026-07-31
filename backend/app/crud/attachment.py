from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment


def list_attachments(
    db: Session,
    *,
    keyword: str | None = None,
    uploader_id: int | None = None,
    storage_driver: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Attachment]:
    from sqlalchemy import or_

    stmt = select(Attachment)
    if uploader_id:
        stmt = stmt.where(Attachment.uploader_id == uploader_id)
    if storage_driver:
        stmt = stmt.where(Attachment.storage_driver == storage_driver)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Attachment.original_filename.like(kw), Attachment.storage_key.like(kw), Attachment.sha256.like(kw)))
    stmt = stmt.order_by(Attachment.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_attachment(
    db: Session,
    *,
    uploader_id: int,
    storage_driver: str,
    storage_key: str,
    original_filename: str,
    content_type: str,
    size: int,
    sha256: str,
) -> Attachment:
    obj = Attachment(
        uploader_id=uploader_id,
        storage_driver=storage_driver,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=content_type,
        size=size,
        sha256=sha256,
    )
    db.add(obj)
    db.flush()
    return obj


def get_attachment_by_id(db: Session, *, attachment_id: int) -> Attachment | None:
    return db.scalar(select(Attachment).where(Attachment.id == attachment_id))


def get_attachments_by_ids(db: Session, ids: list[int]) -> list[Attachment]:
    if not ids:
        return []
    stmt = select(Attachment).where(Attachment.id.in_(ids))
    rows = db.scalars(stmt).all()
    by_id = {a.id: a for a in rows}
    return [by_id[i] for i in ids if i in by_id]


def delete_attachment(db: Session, att: Attachment) -> None:
    db.delete(att)
    db.flush()
