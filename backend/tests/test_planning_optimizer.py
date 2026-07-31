from app.services.planning_optimizer import optimize_plan_schedule


def test_optimize_plan_schedule_missing_plan(session, tenant):
    out = optimize_plan_schedule(session, tenant.id, 999999)
    assert out.get("ok") is False
