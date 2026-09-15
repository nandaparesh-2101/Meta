"""Ad-account structural models: Campaign / AdSet / Ad / Creative.

These mirror the shape of the real Meta Marketing API graph closely enough
that a future `MetaAdsProvider` implementation can populate them directly,
but they do not depend on any Meta SDK type.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class CampaignObjective(str, Enum):
    LEAD_GENERATION = "lead_generation"
    CONVERSIONS = "conversions"
    TRAFFIC = "traffic"
    AWARENESS = "awareness"
    ENGAGEMENT = "engagement"
    SALES = "sales"


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class AudienceType(str, Enum):
    BROAD = "broad"
    INTEREST = "interest"
    LOOKALIKE = "lookalike"
    CUSTOM = "custom"
    RETARGETING = "retargeting"


class Placement(str, Enum):
    FEED = "feed"
    STORY = "story"
    REELS = "reels"
    AUDIENCE_NETWORK = "audience_network"
    MARKETPLACE = "marketplace"


class Device(str, Enum):
    MOBILE = "mobile"
    DESKTOP = "desktop"


class Gender(str, Enum):
    ALL = "all"
    MALE = "male"
    FEMALE = "female"


class CreativeFormat(str, Enum):
    SINGLE_IMAGE = "single_image"
    SINGLE_VIDEO = "single_video"
    CAROUSEL = "carousel"
    COLLECTION = "collection"


class Creative(BaseModel):
    """The creative asset + copy attached to an ad, plus the qualitative
    attributes agents reason about (hook, angle, proof, etc.)."""

    creative_id: str
    ad_id: str
    format: CreativeFormat
    hook: str = Field(..., description="Opening line / first 3 seconds of video")
    visual_description: str
    primary_text: str
    headline: str
    description: str = ""
    cta: str
    emotional_angle: str = Field(..., description="e.g. 'fear of missing out', 'aspiration'")
    problem_stated: str | None = None
    desire_stated: str | None = None
    proof_elements: list[str] = Field(default_factory=list, description="testimonials, stats, etc.")
    offer_stated: str | None = None
    first_used_date: date
    is_active: bool = True


class AudienceDefinition(BaseModel):
    audience_type: AudienceType
    description: str
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: Gender = Gender.ALL
    locations: list[str] = Field(default_factory=list)
    placements: list[Placement] = Field(default_factory=list)
    devices: list[Device] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    lookalike_source: str | None = None
    lookalike_pct: float | None = Field(default=None, ge=0.01, le=0.20)
    estimated_audience_size: int | None = Field(default=None, ge=0)


class AdSet(BaseModel):
    ad_set_id: str
    campaign_id: str
    name: str
    daily_budget: float = Field(..., ge=0)
    audience: AudienceDefinition
    status: CampaignStatus = CampaignStatus.ACTIVE
    created_date: date


class Ad(BaseModel):
    ad_id: str
    ad_set_id: str
    name: str
    creative_id: str
    status: CampaignStatus = CampaignStatus.ACTIVE
    created_date: date


class Campaign(BaseModel):
    campaign_id: str
    name: str
    objective: CampaignObjective
    status: CampaignStatus = CampaignStatus.ACTIVE
    daily_budget: float = Field(..., ge=0)
    created_date: date
