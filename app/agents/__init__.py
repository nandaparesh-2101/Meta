"""The 16 specialist agents plus Guardian.

`AGENT_REGISTRY` maps each agent's canonical name to its class, used by the
orchestrator's router to instantiate only the agents a given workflow needs.
"""

from __future__ import annotations

from app.agents.attribution import AttributionAgent
from app.agents.audience_intelligence import AudienceIntelligenceAgent
from app.agents.base import BaseAgent
from app.agents.budget_scaling import BudgetScalingAgent
from app.agents.business_intelligence import BusinessIntelligenceAgent
from app.agents.campaign_strategist import CampaignStrategistAgent
from app.agents.competitor_intelligence import CompetitorIntelligenceAgent
from app.agents.copy_intelligence import CopyIntelligenceAgent
from app.agents.creative_intelligence import CreativeIntelligenceAgent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.experimentation import ExperimentationAgent
from app.agents.forecasting import ForecastingAgent
from app.agents.funnel_diagnostics import FunnelDiagnosticsAgent
from app.agents.guardian import GuardianAgent
from app.agents.lead_quality import LeadQualityAgent
from app.agents.offer_psychology import OfferPsychologyAgent
from app.agents.optimization import OptimizationAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    BusinessIntelligenceAgent.name: BusinessIntelligenceAgent,
    DataAnalystAgent.name: DataAnalystAgent,
    CampaignStrategistAgent.name: CampaignStrategistAgent,
    AudienceIntelligenceAgent.name: AudienceIntelligenceAgent,
    CreativeIntelligenceAgent.name: CreativeIntelligenceAgent,
    CopyIntelligenceAgent.name: CopyIntelligenceAgent,
    OfferPsychologyAgent.name: OfferPsychologyAgent,
    LeadQualityAgent.name: LeadQualityAgent,
    FunnelDiagnosticsAgent.name: FunnelDiagnosticsAgent,
    ExperimentationAgent.name: ExperimentationAgent,
    BudgetScalingAgent.name: BudgetScalingAgent,
    ForecastingAgent.name: ForecastingAgent,
    AttributionAgent.name: AttributionAgent,
    CompetitorIntelligenceAgent.name: CompetitorIntelligenceAgent,
    OptimizationAgent.name: OptimizationAgent,
}
"""Guardian is intentionally excluded — it has a different (review) contract
and is invoked directly by the orchestrator after recommendations exist."""

__all__ = [
    "AGENT_REGISTRY",
    "BusinessIntelligenceAgent",
    "DataAnalystAgent",
    "CampaignStrategistAgent",
    "AudienceIntelligenceAgent",
    "CreativeIntelligenceAgent",
    "CopyIntelligenceAgent",
    "OfferPsychologyAgent",
    "LeadQualityAgent",
    "FunnelDiagnosticsAgent",
    "ExperimentationAgent",
    "BudgetScalingAgent",
    "ForecastingAgent",
    "AttributionAgent",
    "CompetitorIntelligenceAgent",
    "OptimizationAgent",
    "GuardianAgent",
]
