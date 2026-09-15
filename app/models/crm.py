"""CRM data model.

CRM is NOT connected in this build — `AgentContext.crm_records` is empty by
default. This model exists so `CRMIntelligenceAgent`/`LeadScoringAgent`/
`SalesFeedbackLoopAgent` have a typed shape to consume whenever CRM data is
supplied (e.g. via a future integration or manual import), rather than
reaching into raw dicts.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CRMRecord(BaseModel):
    lead_id: str
    campaign_id: str | None = None
    ad_id: str | None = None
    crm_status: str = Field(..., description="e.g. 'new', 'contacted', 'qualified', 'won', 'lost'")
    deal_value: float | None = Field(default=None, ge=0)
    close_date: date | None = None
    lost_reason: str | None = None
    customer_segment: str | None = None
    notes: str = ""
