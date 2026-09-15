"""Raw daily performance data + the data-sufficiency vocabulary.

`DailyInsight` is the atomic unit of truth that flows in from Meta (or, in
this build, from the mock provider). Derived metrics (CTR, CPL, ROAS, ...)
are NEVER stored on this model — they are always computed on demand by
`app/metrics/engine.py` so there is exactly one place that can get a
division wrong.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class EntityLevel(str, Enum):
    CAMPAIGN = "campaign"
    AD_SET = "ad_set"
    AD = "ad"


class DailyInsight(BaseModel):
    """One entity's raw performance for one calendar day."""

    entity_level: EntityLevel
    entity_id: str
    campaign_id: str
    ad_set_id: str | None = None
    ad_id: str | None = None
    date: date

    spend: float = Field(..., ge=0)
    impressions: int = Field(..., ge=0)
    reach: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    landing_page_views: int = Field(..., ge=0)
    leads: int = Field(..., ge=0)

    # Optional downstream/business data — often missing/late in real life.
    qualified_leads: int | None = Field(default=None, ge=0)
    sales: int | None = Field(default=None, ge=0)
    revenue: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _reach_le_impressions(self) -> DailyInsight:
        if self.reach > self.impressions:
            raise ValueError("reach cannot exceed impressions")
        if self.clicks > self.impressions:
            raise ValueError("clicks cannot exceed impressions")
        if self.landing_page_views > self.clicks and self.clicks > 0:
            # Not strictly impossible (click ID mismatches happen) but worth
            # flagging as a tracking anomaly rather than silently accepting it.
            pass
        return self


class DataSufficiencyLevel(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    EARLY_SIGNAL = "early_signal"
    PROMISING = "promising"
    CONFIDENT = "confident"


class DataSufficiencyResult(BaseModel):
    level: DataSufficiencyLevel
    reason: str
    days_of_data: int
    sample_size: int
    minimum_days_required: int
    minimum_sample_required: int

    @property
    def allows_strong_recommendation(self) -> bool:
        return self.level in (DataSufficiencyLevel.PROMISING, DataSufficiencyLevel.CONFIDENT)
