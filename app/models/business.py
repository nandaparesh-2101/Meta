"""Business-economics models.

Advertising performance is meaningless without the business context behind
it. Agent 01 (Business Intelligence) is responsible for producing these
objects; every other agent that reasons about "good" or "bad" performance
must be given a `KPIConfiguration`/`BusinessConstraints` rather than
inventing thresholds of its own.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SalesProcess(str, Enum):
    SELF_SERVE = "self_serve"
    SALES_ASSISTED = "sales_assisted"
    HIGH_TOUCH = "high_touch"


class BusinessProfile(BaseModel):
    """Raw business facts collected before any ad optimization happens."""

    business_name: str
    business_type: str = Field(..., description="e.g. 'local service', 'ecommerce', 'SaaS'")
    product_or_service: str
    price: float = Field(..., ge=0)
    gross_margin_pct: float = Field(..., ge=0, le=1, description="0.0 - 1.0")
    target_customer: str
    geography: str
    sales_process: SalesProcess
    average_customer_lifetime_value: float = Field(..., ge=0)

    @property
    def gross_profit_per_unit(self) -> float:
        return self.price * self.gross_margin_pct


class KPIConfiguration(BaseModel):
    """Targets that define what "good" looks like for this business."""

    revenue_goal_monthly: float = Field(..., ge=0)
    lead_goal_monthly: int = Field(..., ge=0)
    target_cpl: float = Field(..., gt=0, description="Target cost per lead")
    target_qualified_cpl: float = Field(..., gt=0, description="Target cost per qualified lead")
    target_cac: float = Field(..., gt=0, description="Target customer acquisition cost")
    target_roas: float = Field(..., gt=0, description="Target return on ad spend")

    @model_validator(mode="after")
    def _qualified_cpl_not_below_cpl(self) -> KPIConfiguration:
        if self.target_qualified_cpl < self.target_cpl:
            raise ValueError(
                "target_qualified_cpl cannot be lower than target_cpl "
                "(a qualified lead is a subset of all leads)"
            )
        return self


class BusinessConstraints(BaseModel):
    """Hard limits that no recommendation may violate without approval."""

    max_daily_budget: float | None = Field(default=None, ge=0)
    max_budget_change_pct_per_change: float = Field(
        default=0.20, ge=0, le=5.0, description="Max fractional budget change allowed per action"
    )
    min_data_days_before_scaling: int = Field(default=7, ge=1)
    protected_campaign_ids: list[str] = Field(default_factory=list)
    brand_safety_notes: str | None = None


class BusinessObjective(BaseModel):
    """The synthesized output of Agent 01: what "winning" means right now."""

    profile: BusinessProfile
    kpis: KPIConfiguration
    constraints: BusinessConstraints
    summary: str

    def is_within_cpl_target(self, cpl: float) -> bool:
        return cpl <= self.kpis.target_cpl

    def is_within_qualified_cpl_target(self, qualified_cpl: float) -> bool:
        return qualified_cpl <= self.kpis.target_qualified_cpl

    def is_within_roas_target(self, roas: float) -> bool:
        return roas >= self.kpis.target_roas
