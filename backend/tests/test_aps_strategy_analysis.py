from app.services.aps_strategy_analysis import analyze_aps_strategies


def test_aps_strategy_missing_plan(session, tenant):
    try:
        analyze_aps_strategies(session, tenant.id, 999999, 0)
        assert False, "should raise"
    except ValueError:
        pass
