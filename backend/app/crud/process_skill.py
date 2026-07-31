from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.employee_skill import Skill
from app.models.process import Process
from app.models.process_skill import ProcessSkillLink


def list_process_skill_ids(db: Session, process_id: int) -> list[int]:
    rows = db.scalars(
        select(ProcessSkillLink.skill_id).where(
            ProcessSkillLink.process_id == process_id,
        )
    ).all()
    return list(dict.fromkeys(int(x) for x in rows))


def list_process_skills(db: Session, process_id: int) -> list[Skill]:
    return list(
        db.scalars(
            select(Skill)
            .join(ProcessSkillLink, ProcessSkillLink.skill_id == Skill.id)
            .where(
                ProcessSkillLink.process_id == process_id,
                Skill.is_active.is_(True),
            )
            .order_by(Skill.id.asc())
        ).all()
    )


def get_process_skills_map(db: Session, process_ids: list[int]) -> dict[int, list[int]]:
    if not process_ids:
        return {}
    rows = db.execute(
        select(ProcessSkillLink.process_id, ProcessSkillLink.skill_id).where(
            ProcessSkillLink.process_id.in_(process_ids),
        )
    ).all()
    out: dict[int, list[int]] = {}
    for pid, sid in rows:
        out.setdefault(int(pid), []).append(int(sid))
    for k in out:
        out[k] = list(dict.fromkeys(out[k]))
    return out


def replace_process_skills(db: Session, process_id: int, skill_ids: list[int]) -> list[int]:
    proc = db.scalar(select(Process.id).where(Process.id == process_id))
    if not proc:
        raise ValueError("工序不存在")
    ids = [int(x) for x in skill_ids if int(x) > 0]
    ids = list(dict.fromkeys(ids))
    if ids:
        valid = {
            int(x)
            for x in db.scalars(
                select(Skill.id).where(Skill.id.in_(ids), Skill.is_active.is_(True))
            ).all()
        }
        ids = [x for x in ids if x in valid]
    db.execute(
        delete(ProcessSkillLink).where(
            ProcessSkillLink.process_id == process_id,
        )
    )
    for sid in ids:
        db.add(ProcessSkillLink(process_id=process_id, skill_id=sid))
    db.flush()
    return ids
