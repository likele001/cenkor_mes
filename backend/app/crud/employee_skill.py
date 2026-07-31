from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.employee_skill import Skill, UserSkillLink


def list_skills(
    db: Session,
    keyword: str | None = None,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 200,
) -> list[Skill]:
    stmt = select(Skill)
    if not include_inactive:
        stmt = stmt.where(Skill.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Skill.code.like(kw), Skill.name.like(kw)))
    stmt = stmt.order_by(Skill.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def get_skill_by_id(db: Session, skill_id: int) -> Skill | None:
    return db.scalar(select(Skill).where(Skill.id == skill_id))


def get_skill_by_code(db: Session, code: str) -> Skill | None:
    return db.scalar(select(Skill).where(Skill.code == code))


def create_skill(db: Session, code: str, name: str, is_active: bool) -> Skill:
    obj = Skill(code=code, name=name, is_active=is_active)
    db.add(obj)
    db.flush()
    return obj


def update_skill(db: Session, obj: Skill, code: str | None = None, name: str | None = None, is_active: bool | None = None) -> Skill:
    if code is not None:
        obj.code = code
    if name is not None:
        obj.name = name
    if is_active is not None:
        obj.is_active = is_active
    db.flush()
    return obj


def list_user_skill_ids(db: Session, user_id: int) -> list[int]:
    return [x[0] for x in db.execute(select(UserSkillLink.skill_id).where(UserSkillLink.user_id == user_id)).all()]


def set_user_skills(db: Session, user_id: int, skill_ids: list[int]) -> None:
    skill_ids = [int(x) for x in skill_ids if int(x) > 0]
    skill_ids = list(dict.fromkeys(skill_ids))

    if skill_ids:
        exists = db.scalars(select(Skill.id).where(Skill.id.in_(skill_ids))).all()
        if len(exists) != len(skill_ids):
            raise ValueError("技能不存在")

    db.execute(delete(UserSkillLink).where(UserSkillLink.user_id == user_id))
    for sid in skill_ids:
        db.add(UserSkillLink(user_id=user_id, skill_id=sid))
    db.flush()
