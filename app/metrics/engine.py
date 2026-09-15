"""Reusable, defensive metric calculations.

Single source of truth for every derived advertising/business metric. Rules:

* Never raise on a zero-denominator — return `None` and let the caller decide
  how to present "not calculable" (never silently coerce to 0.0, which reads
  as "perfect performance").
* Never fabricate a metric from missing data. If leads is 0 but revenue is
  reported, that's an anomaly for the caller to flag, not something this
  module papers over.
* All functions are pure and stateless so they are trivially unit-testable.
"""

from __future__ import annotations

from app.models.metrics import DailyInsight


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def ctr(clicks: int, impressions: int) -> float | None:
    """Click-through rate, as a fraction (0.02 = 2%)."""
    return _safe_div(clicks, impressions)


def cpc(spend: float, clicks: int) -> float | None:
    return _safe_div(spend, clicks)


def cpm(spend: float, impressions: int) -> float | None:
    v = _safe_div(spend, impressions)
    return v * 1000 if v is not None else None


def frequency(impressions: int, reach: int) -> float | None:
    return _safe_div(impressions, reach)


def cpl(spend: float, leads: int) -> float | None:
    return _safe_div(spend, leads)


def landing_page_conversion_rate(leads: int, landing_page_views: int) -> float | None:
    return _safe_div(leads, landing_page_views)


def click_to_lead_rate(leads: int, clicks: int) -> float | None:
    return _safe_div(leads, clicks)


def qualified_rate(qualified_leads: int | None, leads: int) -> float | None:
    return _safe_div(qualified_leads, leads)


def qualified_cpl(spend: float, qualified_leads: int | None) -> float | None:
    return _safe_div(spend, qualified_leads)


def cost_per_appointment(spend: float, appointments: int) -> float | None:
    return _safe_div(spend, appointments)


def cac(spend: float, sales: int | None) -> float | None:
    """Customer acquisition cost."""
    return _safe_div(spend, sales)


def roas(revenue: float | None, spend: float) -> float | None:
    return _safe_div(revenue, spend)


def revenue_per_lead(revenue: float | None, leads: int) -> float | None:
    return _safe_div(revenue, leads)


def revenue_per_qualified_lead(revenue: float | None, qualified_leads: int | None) -> float | None:
    return _safe_div(revenue, qualified_leads)


def close_rate(sales: int | None, leads: int) -> float | None:
    return _safe_div(sales, leads)


class MetricSnapshot:
    """Computes and holds every derived metric for one insight or one
    aggregated window of insights. Immutable once built."""

    def __init__(self, spend: float, impressions: int, reach: int, clicks: int,
                 landing_page_views: int, leads: int, qualified_leads: int | None,
                 sales: int | None, revenue: float | None) -> None:
        self.spend = spend
        self.impressions = impressions
        self.reach = reach
        self.clicks = clicks
        self.landing_page_views = landing_page_views
        self.leads = leads
        self.qualified_leads = qualified_leads
        self.sales = sales
        self.revenue = revenue

        self.ctr = ctr(clicks, impressions)
        self.cpc = cpc(spend, clicks)
        self.cpm = cpm(spend, impressions)
        self.frequency = frequency(impressions, reach)
        self.cpl = cpl(spend, leads)
        self.landing_page_conversion_rate = landing_page_conversion_rate(leads, landing_page_views)
        self.click_to_lead_rate = click_to_lead_rate(leads, clicks)
        self.qualified_rate = qualified_rate(qualified_leads, leads)
        self.qualified_cpl = qualified_cpl(spend, qualified_leads)
        self.cac = cac(spend, sales)
        self.roas = roas(revenue, spend)
        self.revenue_per_lead = revenue_per_lead(revenue, leads)
        self.revenue_per_qualified_lead = revenue_per_qualified_lead(revenue, qualified_leads)
        self.close_rate = close_rate(sales, leads)

    @classmethod
    def from_insight(cls, insight: DailyInsight) -> MetricSnapshot:
        return cls(
            spend=insight.spend,
            impressions=insight.impressions,
            reach=insight.reach,
            clicks=insight.clicks,
            landing_page_views=insight.landing_page_views,
            leads=insight.leads,
            qualified_leads=insight.qualified_leads,
            sales=insight.sales,
            revenue=insight.revenue,
        )

    @classmethod
    def aggregate(cls, insights: list[DailyInsight]) -> MetricSnapshot:
        """Sum raw counters across a window, THEN derive ratios — never
        average pre-computed ratios (that's a classic metrics bug)."""
        if not insights:
            return cls(0, 0, 0, 0, 0, 0, None, None, None)

        has_qualified = any(i.qualified_leads is not None for i in insights)
        has_sales = any(i.sales is not None for i in insights)
        has_revenue = any(i.revenue is not None for i in insights)

        snapshot = cls(
            spend=sum(i.spend for i in insights),
            impressions=sum(i.impressions for i in insights),
            reach=max((i.reach for i in insights), default=0),
            clicks=sum(i.clicks for i in insights),
            landing_page_views=sum(i.landing_page_views for i in insights),
            leads=sum(i.leads for i in insights),
            qualified_leads=(sum(i.qualified_leads or 0 for i in insights) if has_qualified else None),
            sales=(sum(i.sales or 0 for i in insights) if has_sales else None),
            revenue=(sum(i.revenue or 0.0 for i in insights) if has_revenue else None),
        )
        # Frequency (impressions/reach) does not aggregate correctly across a
        # multi-day window the way spend/leads/clicks do: reach is a
        # deduplicated headcount, so summing daily impressions over a
        # deduplicated single-day-max reach systematically inflates frequency
        # as the window grows. An impressions-weighted average of each day's
        # own (correctly-scoped) frequency is a far more honest estimate.
        snapshot.frequency = _weighted_average_daily_frequency(insights)
        return snapshot

    def as_dict(self) -> dict:
        return {
            "spend": self.spend,
            "impressions": self.impressions,
            "reach": self.reach,
            "clicks": self.clicks,
            "landing_page_views": self.landing_page_views,
            "leads": self.leads,
            "qualified_leads": self.qualified_leads,
            "sales": self.sales,
            "revenue": self.revenue,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "frequency": self.frequency,
            "cpl": self.cpl,
            "landing_page_conversion_rate": self.landing_page_conversion_rate,
            "click_to_lead_rate": self.click_to_lead_rate,
            "qualified_rate": self.qualified_rate,
            "qualified_cpl": self.qualified_cpl,
            "cac": self.cac,
            "roas": self.roas,
            "revenue_per_lead": self.revenue_per_lead,
            "revenue_per_qualified_lead": self.revenue_per_qualified_lead,
            "close_rate": self.close_rate,
        }


def _weighted_average_daily_frequency(insights: list[DailyInsight]) -> float | None:
    weighted_sum = 0.0
    total_weight = 0
    for i in insights:
        if i.reach <= 0:
            continue
        weighted_sum += (i.impressions / i.reach) * i.impressions
        total_weight += i.impressions
    return (weighted_sum / total_weight) if total_weight else None


def pct_change(old: float | None, new: float | None) -> float | None:
    """Relative change from old -> new, as a fraction. None if not calculable."""
    if old is None or new is None or old == 0:
        return None
    return (new - old) / abs(old)
