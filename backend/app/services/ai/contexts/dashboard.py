from sqlalchemy.orm import Session

from app.services.ai.contexts.factory import build_factory_context


def build_boss_context(db: Session, tenant_id: int, *, plan_id: int | None = None) -> dict:
    return build_factory_context(db, tenant_id, plan_id=plan_id)
