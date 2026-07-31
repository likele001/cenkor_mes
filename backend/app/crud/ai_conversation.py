from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage


def create_conversation(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    scene: str,
    title: str | None = None,
    context_id: int | None = None,
) -> AiConversation:
    conv = AiConversation(
        tenant_id=tenant_id,
        user_id=user_id,
        scene=scene,
        title=title,
        context_id=context_id,
    )
    db.add(conv)
    db.flush()
    return conv


def get_conversation(db: Session, tenant_id: int, conversation_id: int) -> AiConversation | None:
    row = db.get(AiConversation, conversation_id)
    if not row or row.tenant_id != tenant_id:
        return None
    return row


def list_messages(db: Session, conversation_id: int, limit: int = 20) -> list[AiMessage]:
    return list(
        db.scalars(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.id.asc())
            .limit(limit)
        ).all()
    )


def add_message(
    db: Session,
    *,
    conversation_id: int,
    role: str,
    content: str,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> AiMessage:
    msg = AiMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    db.add(msg)
    db.flush()
    conv = db.get(AiConversation, conversation_id)
    if conv and role == "user" and not conv.title:
        conv.title = content.strip()[:30] or None
    return msg


def list_conversations(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    scene: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[AiConversation]:
    stmt = select(AiConversation).where(AiConversation.tenant_id == tenant_id, AiConversation.user_id == user_id)
    if scene:
        stmt = stmt.where(AiConversation.scene == scene)
    stmt = stmt.order_by(AiConversation.updated_at.desc(), AiConversation.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def delete_conversation(db: Session, tenant_id: int, conversation_id: int) -> bool:
    conv = get_conversation(db, tenant_id, conversation_id)
    if not conv:
        return False
    db.execute(delete(AiMessage).where(AiMessage.conversation_id == conversation_id))
    db.delete(conv)
    db.flush()
    return True
