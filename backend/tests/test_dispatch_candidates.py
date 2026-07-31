"""派工候选人筛选"""

from app.models.user import User, user_roles
from app.services.dispatch_candidates import list_dispatch_candidate_users


def test_dispatch_candidates_employee_only(session, tenant, admin_role, employee_role):
    admin = User(
        tenant_id=tenant.id,
        username="admin1",
        password_hash="x",
        full_name="管理员",
        is_active=True,
    )
    worker = User(
        tenant_id=tenant.id,
        username="emp1",
        password_hash="x",
        full_name="员工甲",
        is_active=True,
    )
    session.add_all([admin, worker])
    session.flush()
    session.execute(user_roles.insert().values(user_id=admin.id, role_id=admin_role.id))
    session.execute(user_roles.insert().values(user_id=worker.id, role_id=employee_role.id))
    session.flush()

    rows = list_dispatch_candidate_users(session, tenant.id)
    ids = {u.id for u in rows}
    assert worker.id in ids
    assert admin.id not in ids
