from __future__ import annotations

from app.models.business import BusinessConstraints, KPIConfiguration
from app.models.metrics import DataSufficiencyLevel
from app.rules.kpi_rules import KPIStatus, evaluate_cpl, evaluate_roas
from app.rules.scaling_rules import is_scaling_change_safe, max_allowed_budget_change_pct


def _kpis(**overrides) -> KPIConfiguration:
    base = dict(
        revenue_goal_monthly=10000.0,
        lead_goal_monthly=100,
        target_cpl=25.0,
        target_qualified_cpl=60.0,
        target_cac=300.0,
        target_roas=3.0,
    )
    base.update(overrides)
    return KPIConfiguration(**base)


def test_evaluate_cpl_on_target():
    assert evaluate_cpl(20.0, _kpis()) == KPIStatus.ON_TARGET


def test_evaluate_cpl_borderline():
    assert evaluate_cpl(27.0, _kpis()) == KPIStatus.BORDERLINE


def test_evaluate_cpl_off_target():
    assert evaluate_cpl(50.0, _kpis()) == KPIStatus.OFF_TARGET


def test_evaluate_cpl_not_calculable():
    assert evaluate_cpl(None, _kpis()) == KPIStatus.NOT_CALCULABLE


def test_evaluate_roas_direction_is_inverted_vs_cpl():
    assert evaluate_roas(4.0, _kpis()) == KPIStatus.ON_TARGET
    assert evaluate_roas(1.0, _kpis()) == KPIStatus.OFF_TARGET


def test_kpi_configuration_rejects_qualified_cpl_below_cpl():
    import pytest

    with pytest.raises(ValueError):
        _kpis(target_qualified_cpl=10.0, target_cpl=25.0)


def test_max_allowed_budget_change_scales_with_sufficiency():
    constraints = BusinessConstraints(max_budget_change_pct_per_change=0.20)
    assert max_allowed_budget_change_pct(constraints, DataSufficiencyLevel.INSUFFICIENT_DATA) == 0.0
    assert max_allowed_budget_change_pct(constraints, DataSufficiencyLevel.CONFIDENT) == 0.20


def test_scaling_blocked_before_min_days():
    constraints = BusinessConstraints(min_data_days_before_scaling=7)
    is_safe, reason = is_scaling_change_safe(
        current_daily_budget=100.0, proposed_daily_budget=120.0, constraints=constraints,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT, days_running=3,
    )
    assert not is_safe
    assert "days running" in reason.lower() or "requires" in reason.lower()


def test_scaling_blocked_when_change_exceeds_ceiling():
    constraints = BusinessConstraints(min_data_days_before_scaling=1, max_budget_change_pct_per_change=0.10)
    is_safe, reason = is_scaling_change_safe(
        current_daily_budget=100.0, proposed_daily_budget=200.0, constraints=constraints,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT, days_running=10,
    )
    assert not is_safe


def test_scaling_allowed_within_bounds():
    constraints = BusinessConstraints(min_data_days_before_scaling=1, max_budget_change_pct_per_change=0.30)
    is_safe, _ = is_scaling_change_safe(
        current_daily_budget=100.0, proposed_daily_budget=115.0, constraints=constraints,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT, days_running=10,
    )
    assert is_safe


def test_scaling_blocked_above_hard_cap():
    constraints = BusinessConstraints(
        min_data_days_before_scaling=1, max_budget_change_pct_per_change=1.0, max_daily_budget=100.0
    )
    is_safe, reason = is_scaling_change_safe(
        current_daily_budget=90.0, proposed_daily_budget=150.0, constraints=constraints,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT, days_running=10,
    )
    assert not is_safe
    assert "hard cap" in reason
