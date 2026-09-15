from __future__ import annotations

from datetime import date

from app.metrics import engine
from app.models.metrics import DailyInsight, EntityLevel


def test_ctr_normal():
    assert engine.ctr(50, 1000) == 0.05


def test_ctr_zero_impressions_returns_none():
    assert engine.ctr(10, 0) is None


def test_cpl_zero_leads_returns_none():
    assert engine.cpl(100.0, 0) is None


def test_cpm_computation():
    assert engine.cpm(10.0, 1000) == 10.0


def test_roas_none_revenue():
    assert engine.roas(None, 100.0) is None


def test_qualified_cpl_none_when_qualified_leads_none():
    assert engine.qualified_cpl(100.0, None) is None


def test_pct_change_basic():
    assert engine.pct_change(100.0, 120.0) == 0.2


def test_pct_change_zero_old_returns_none():
    assert engine.pct_change(0.0, 100.0) is None


def _insight(**overrides) -> DailyInsight:
    base = dict(
        entity_level=EntityLevel.CAMPAIGN,
        entity_id="c1",
        campaign_id="c1",
        date=date(2026, 1, 1),
        spend=100.0,
        impressions=10000,
        reach=8000,
        clicks=200,
        landing_page_views=150,
        leads=10,
        qualified_leads=5,
        sales=1,
        revenue=150.0,
    )
    base.update(overrides)
    return DailyInsight(**base)


def test_snapshot_from_insight():
    snapshot = engine.MetricSnapshot.from_insight(_insight())
    assert snapshot.ctr == 0.02
    assert snapshot.cpl == 10.0
    assert snapshot.qualified_cpl == 20.0
    assert snapshot.roas == 1.5


def test_aggregate_sums_raw_then_derives_ratios():
    day1 = _insight(spend=100.0, clicks=100, impressions=10000, leads=10)
    day2 = _insight(spend=100.0, clicks=300, impressions=10000, leads=30, date=date(2026, 1, 2))
    agg = engine.MetricSnapshot.aggregate([day1, day2])
    # Aggregate CTR must be computed from summed clicks/impressions, not averaged per-day ratios.
    assert agg.spend == 200.0
    assert agg.leads == 40
    assert agg.ctr == (400 / 20000)


def test_aggregate_empty_list_is_safe():
    agg = engine.MetricSnapshot.aggregate([])
    assert agg.spend == 0
    assert agg.cpl is None


def test_reach_cannot_exceed_impressions():
    import pytest

    with pytest.raises(ValueError):
        _insight(reach=99999, impressions=1000)
