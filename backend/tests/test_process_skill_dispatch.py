"""工序-技能绑定与派工过滤"""

from app.models.employee_skill import Skill, UserSkillLink
from app.models.process import Process
from app.models.process_skill import ProcessSkillLink
from app.services.dispatch_candidates import (
    build_user_department_map,
    build_user_skill_map,
    filter_candidates_for_task,
)


def test_replace_process_skills(session, tenant, test_user):
    from app.crud.process_skill import list_process_skill_ids, replace_process_skills
    from app.crud.process import create_process

    proc = create_process(
        session, tenant_id=tenant.id, code="P-SK", name="技能工序", workshop="冲压", std_minutes=10, is_active=True
    )
    sk = Skill(tenant_id=tenant.id, code="SK1", name="焊接", is_active=True)
    session.add(sk)
    session.flush()

    ids = replace_process_skills(session, tenant.id, proc.id, [sk.id])
    session.commit()
    assert ids == [sk.id]
    assert list_process_skill_ids(session, tenant.id, proc.id) == [sk.id]


def test_filter_candidates_by_skill(session, tenant, employee_role):
    from app.models.role import Role
    from app.models.user import User, user_roles

    sk = Skill(tenant_id=tenant.id, code="SK2", name="冲压", is_active=True)
    u1 = User(tenant_id=tenant.id, username="e1", password_hash="x", full_name="员工1", is_active=True, is_superuser=False)
    u2 = User(tenant_id=tenant.id, username="e2", password_hash="x", full_name="员工2", is_active=True, is_superuser=False)
    session.add_all([sk, u1, u2])
    session.flush()
    session.execute(user_roles.insert().values(user_id=u1.id, role_id=employee_role.id))
    session.execute(user_roles.insert().values(user_id=u2.id, role_id=employee_role.id))
    session.add(UserSkillLink(tenant_id=tenant.id, user_id=u1.id, skill_id=sk.id))
    session.commit()

    candidates = [{"id": u1.id, "name": "员工1"}, {"id": u2.id, "name": "员工2"}]
    skill_map = build_user_skill_map(session, tenant.id, [u1.id, u2.id])
    dept_map = build_user_department_map(session, tenant.id, [u1.id, u2.id])
    filtered = filter_candidates_for_task(
        candidates,
        required_skill_ids=[sk.id],
        user_skill_map=skill_map,
        workshop="冲压",
        user_dept_map=dept_map,
    )
    assert len(filtered) == 1
    assert filtered[0]["id"] == u1.id
