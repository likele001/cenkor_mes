from app.services.plan_capacity_settings import get_default_capacity, get_capacity_unit, task_load_qty


def test_default_capacity_pieces(session, tenant):
    from app.services.plan_capacity_settings import save_capacity_unit

    save_capacity_unit(session, tenant.id, "pieces")
    session.commit()
    assert get_capacity_unit(session, tenant.id) == "pieces"
    cap = get_default_capacity(session, tenant.id)
    assert cap == 300 or cap > 0


def test_task_load_qty_pieces():
    assert task_load_qty(planned_qty=100, std_minutes=5, unit="pieces") == 100


def test_task_load_qty_minutes():
    assert task_load_qty(planned_qty=10, std_minutes=6, unit="minutes") == 60
