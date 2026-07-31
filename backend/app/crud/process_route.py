from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.process_route import ProcessRoute, ProcessRouteStep


def get_route_by_id(db: Session, route_id: int) -> ProcessRoute | None:
    return db.scalar(select(ProcessRoute).where(ProcessRoute.id == route_id))


def list_routes(
    db: Session,
    product_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[ProcessRoute]:
    stmt = select(ProcessRoute)
    if product_id is not None:
        stmt = stmt.where(ProcessRoute.product_id == product_id)
    if not include_inactive:
        stmt = stmt.where(ProcessRoute.is_active.is_(True))
    stmt = stmt.order_by(ProcessRoute.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_route(
    db: Session,
    product_id: int,
    name: str,
    is_default: bool,
    is_active: bool,
    steps: list[tuple[int, int]],
) -> ProcessRoute:
    if is_default:
        db.execute(
            update(ProcessRoute)
            .where(ProcessRoute.product_id == product_id)
            .values(is_default=False)
        )

    item = ProcessRoute(
        product_id=product_id,
        name=name,
        is_default=is_default,
        is_active=is_active,
    )
    item.steps = [ProcessRouteStep(seq=seq, process_id=process_id) for seq, process_id in steps]
    db.add(item)
    db.flush()
    return item


def update_route(
    db: Session,
    item: ProcessRoute,
    name: str | None = None,
    is_default: bool | None = None,
    is_active: bool | None = None,
    steps: list[tuple[int, int]] | None = None,
) -> ProcessRoute:
    if name is not None:
        item.name = name
    if is_active is not None:
        item.is_active = is_active
    if is_default is not None:
        item.is_default = is_default
        if is_default:
            db.execute(
                update(ProcessRoute)
                .where(
                    ProcessRoute.product_id == item.product_id,
                    ProcessRoute.id != item.id,
                )
                .values(is_default=False)
            )
    if steps is not None:
        item.steps = [ProcessRouteStep(seq=seq, process_id=process_id) for seq, process_id in steps]
    db.flush()
    return item


def get_default_route_for_product(db: Session, product_id: int) -> ProcessRoute:
    route = db.scalar(
        select(ProcessRoute)
        .where(
            ProcessRoute.product_id == product_id,
            ProcessRoute.is_default.is_(True),
            ProcessRoute.is_active.is_(True),
        )
        .options(selectinload(ProcessRoute.steps))
    )
    if not route or not route.steps:
        raise ValueError("产品默认工艺路线未配置")
    return route


def get_first_default_route_template(db: Session) -> ProcessRoute | None:
    """租户内第一个有工序的默认工艺路线，用于新产品克隆。"""
    routes = db.scalars(
        select(ProcessRoute)
        .where(
            ProcessRoute.is_default.is_(True),
            ProcessRoute.is_active.is_(True),
        )
        .options(selectinload(ProcessRoute.steps))
        .order_by(ProcessRoute.id.asc())
    ).all()
    for route in routes:
        if route.steps:
            return route
    return None


def clone_default_route_to_product(db: Session, product_id: int, template: ProcessRoute) -> ProcessRoute:
    steps = [(s.seq, s.process_id) for s in sorted(template.steps, key=lambda x: x.seq)]
    return create_route(
        db,
        product_id=product_id,
        name="默认路线",
        is_default=True,
        is_active=True,
        steps=steps,
    )
