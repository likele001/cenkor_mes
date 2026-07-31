import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_invite import TenantInvite


def _make_token() -> str:
    return secrets.token_urlsafe(24)


def create_invite(
    db: Session,
    role_code: str,
    max_uses: int,
    expires_at: datetime | None,
    created_by: int | None,
) -> TenantInvite:
    inv = TenantInvite(
        token=_make_token(),
        role_code=role_code,
        max_uses=max_uses,
        used_count=0,
        expires_at=expires_at,
        created_by=created_by,
    )
    db.add(inv)
    db.flush()
    return inv


def get_invite_by_token(db: Session, token: str) -> TenantInvite | None:
    return db.scalar(select(TenantInvite).where(TenantInvite.token == token))


def list_invites(db: Session) -> list[TenantInvite]:
    return list(
        db.scalars(
            select(TenantInvite).order_by(TenantInvite.id.desc())
        ).all()
    )


def consume_invite(db: Session, invite: TenantInvite) -> None:
    if invite.expires_at and invite.expires_at < datetime.now():
        raise ValueError("邀请已过期")
    if invite.used_count >= invite.max_uses:
        raise ValueError("邀请已达使用上限")
    invite.used_count += 1
    db.flush()
