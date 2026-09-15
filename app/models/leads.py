"""Lead-to-revenue funnel models.

Lead -> Contacted -> Qualified -> Appointment -> Opportunity -> Sale -> Revenue
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class FunnelStage(str, Enum):
    LEAD = "lead"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    APPOINTMENT = "appointment"
    OPPORTUNITY = "opportunity"
    SALE = "sale"

    @property
    def order(self) -> int:
        return list(FunnelStage).index(self)


class Lead(BaseModel):
    lead_id: str
    ad_id: str
    ad_set_id: str
    campaign_id: str
    created_at: datetime
    stage: FunnelStage = FunnelStage.LEAD
    contacted_at: datetime | None = None
    qualified_at: datetime | None = None
    appointment_at: datetime | None = None
    disqualification_reason: str | None = None
    response_time_minutes: float | None = Field(
        default=None, ge=0, description="Time from lead creation to first contact"
    )


class QualifiedLead(BaseModel):
    lead_id: str
    qualified_at: datetime
    qualification_score: float | None = Field(default=None, ge=0, le=1)
    qualification_notes: str = ""


class Sale(BaseModel):
    sale_id: str
    lead_id: str
    ad_id: str
    ad_set_id: str
    campaign_id: str
    sale_date: date
    amount: float = Field(..., ge=0)


class Revenue(BaseModel):
    """Aggregated revenue attributable to an entity over a window."""

    entity_id: str
    campaign_id: str
    window_start: date
    window_end: date
    total_revenue: float = Field(..., ge=0)
    total_sales: int = Field(..., ge=0)
