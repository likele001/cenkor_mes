from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.ai import PlatformAiGateway, PlatformAiModel, PlatformAiProfile

SECRET_PLACEHOLDER = "******"
PROFILE_ID = 1


def get_ai_profile(db: Session) -> PlatformAiProfile | None:
    return db.get(PlatformAiProfile, PROFILE_ID)


def ensure_ai_profile(db: Session) -> PlatformAiProfile:
    row = get_ai_profile(db)
    if row:
        return row
    row = PlatformAiProfile(id=PROFILE_ID, enabled=False, base_url="", api_key=None, timeout_seconds=120)
    db.add(row)
    db.flush()
    return row


def update_ai_global_enabled(db: Session, *, enabled: bool) -> PlatformAiProfile:
    row = ensure_ai_profile(db)
    row.enabled = enabled
    db.flush()
    return row


def is_ai_globally_enabled(db: Session) -> bool:
    from app.core.config import settings

    row = ensure_ai_profile(db)
    return bool(row.enabled) or bool(settings.AI_ENABLED)


# --- gateways ---


def list_ai_gateways(db: Session) -> list[PlatformAiGateway]:
    return list(
        db.scalars(
            select(PlatformAiGateway).order_by(PlatformAiGateway.sort_order.asc(), PlatformAiGateway.id.asc())
        ).all()
    )


def get_ai_gateway_by_id(db: Session, gateway_id: int) -> PlatformAiGateway | None:
    return db.get(PlatformAiGateway, gateway_id)


def get_ai_gateway_by_code(db: Session, code: str) -> PlatformAiGateway | None:
    return db.scalar(select(PlatformAiGateway).where(PlatformAiGateway.code == code))


def get_default_ai_gateway(db: Session) -> PlatformAiGateway | None:
    row = db.scalar(
        select(PlatformAiGateway)
        .where(PlatformAiGateway.is_default.is_(True), PlatformAiGateway.enabled.is_(True))
        .limit(1)
    )
    if row:
        return row
    return db.scalar(
        select(PlatformAiGateway)
        .where(PlatformAiGateway.enabled.is_(True))
        .order_by(PlatformAiGateway.sort_order.asc())
        .limit(1)
    )


def create_ai_gateway(
    db: Session,
    *,
    code: str,
    display_name: str,
    base_url: str,
    api_key: str | None = None,
    enabled: bool = True,
    timeout_seconds: int = 120,
    sort_order: int = 0,
    is_default: bool = False,
) -> PlatformAiGateway:
    if is_default:
        db.execute(update(PlatformAiGateway).values(is_default=False))
    row = PlatformAiGateway(
        code=code.strip(),
        display_name=display_name.strip(),
        base_url=base_url.strip().rstrip("/"),
        api_key=(api_key or "").strip() or None,
        enabled=enabled,
        timeout_seconds=int(timeout_seconds),
        sort_order=sort_order,
        is_default=is_default,
    )
    db.add(row)
    db.flush()
    return row


def update_ai_gateway(db: Session, row: PlatformAiGateway, **fields) -> PlatformAiGateway:
    if fields.get("is_default"):
        db.execute(update(PlatformAiGateway).where(PlatformAiGateway.id != row.id).values(is_default=False))
    if "base_url" in fields and fields["base_url"] is not None:
        fields["base_url"] = str(fields["base_url"]).strip().rstrip("/")
    if "api_key" in fields and fields["api_key"] is not None:
        k = str(fields["api_key"]).strip()
        if not k or k == SECRET_PLACEHOLDER:
            fields.pop("api_key", None)
        else:
            fields["api_key"] = k
    for k, v in fields.items():
        if v is not None and hasattr(row, k):
            setattr(row, k, v)
    db.flush()
    return row


def set_default_ai_gateway(db: Session, row: PlatformAiGateway) -> PlatformAiGateway:
    db.execute(update(PlatformAiGateway).values(is_default=False))
    row.is_default = True
    row.enabled = True
    db.flush()
    return row


def delete_ai_gateway(db: Session, row: PlatformAiGateway) -> None:
    db.delete(row)


# --- models ---


def list_ai_models(db: Session, gateway_id: int | None = None) -> list[PlatformAiModel]:
    stmt = select(PlatformAiModel).order_by(PlatformAiModel.sort_order.asc(), PlatformAiModel.id.asc())
    if gateway_id is not None:
        stmt = stmt.where(PlatformAiModel.gateway_id == gateway_id)
    return list(db.scalars(stmt).all())


def get_ai_model_by_id(db: Session, model_id: int) -> PlatformAiModel | None:
    return db.get(PlatformAiModel, model_id)


def get_default_ai_model(db: Session) -> PlatformAiModel | None:
    row = db.scalar(
        select(PlatformAiModel).where(PlatformAiModel.is_default.is_(True), PlatformAiModel.is_active.is_(True)).limit(1)
    )
    if row:
        return row
    gw = get_default_ai_gateway(db)
    if not gw:
        return None
    return db.scalar(
        select(PlatformAiModel)
        .where(PlatformAiModel.gateway_id == gw.id, PlatformAiModel.is_active.is_(True))
        .order_by(PlatformAiModel.sort_order.asc())
        .limit(1)
    )


def get_default_vision_model(db: Session) -> PlatformAiModel | None:
    row = db.scalar(
        select(PlatformAiModel)
        .where(PlatformAiModel.is_vision.is_(True), PlatformAiModel.is_active.is_(True))
        .order_by(PlatformAiModel.is_default.desc(), PlatformAiModel.sort_order.asc())
        .limit(1)
    )
    if row:
        return row
    return get_default_ai_model(db)


def create_ai_model(
    db: Session,
    *,
    gateway_id: int,
    code: str,
    display_name: str,
    model_id: str,
    is_vision: bool = False,
    is_active: bool = True,
    sort_order: int = 0,
    is_default: bool = False,
) -> PlatformAiModel:
    if is_default:
        db.execute(update(PlatformAiModel).values(is_default=False))
    row = PlatformAiModel(
        gateway_id=gateway_id,
        code=code.strip(),
        display_name=display_name.strip(),
        model_id=model_id.strip(),
        is_vision=is_vision,
        is_active=is_active,
        sort_order=sort_order,
        is_default=is_default,
    )
    db.add(row)
    db.flush()
    return row


def update_ai_model(db: Session, row: PlatformAiModel, **fields) -> PlatformAiModel:
    if fields.get("is_default"):
        db.execute(update(PlatformAiModel).values(is_default=False))
    for k, v in fields.items():
        if v is not None and hasattr(row, k):
            setattr(row, k, v)
    db.flush()
    return row


def set_default_ai_model(db: Session, row: PlatformAiModel) -> PlatformAiModel:
    db.execute(update(PlatformAiModel).values(is_default=False))
    row.is_default = True
    row.is_active = True
    db.flush()
    return row


def delete_ai_model(db: Session, row: PlatformAiModel) -> None:
    db.delete(row)
