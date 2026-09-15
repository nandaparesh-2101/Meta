"""70 specialist agents plus Guardian (16 core agents + a V2 expansion of
54 advanced specialists across customer intelligence, creative generation,
creative operations, landing/funnel/sales, data quality, positioning/offer,
funnel economics, verification, learning intelligence, governance, and
prioritization).

`AGENT_REGISTRY` maps each agent's canonical name to its class — used by
the orchestrator's router to instantiate only the agents a given workflow
needs. For the richer metadata (tier, capabilities, dependencies, priority,
enabled/disabled) consumed by observability/documentation tooling, see
`app.agents.registry.AGENT_CATALOG`.
"""

from __future__ import annotations

# -- Core 16 (+ Guardian) --------------------------------------------------
from app.agents.attribution import AttributionAgent
from app.agents.audience_intelligence import AudienceIntelligenceAgent
from app.agents.base import BaseAgent
from app.agents.budget_scaling import BudgetScalingAgent
from app.agents.business_intelligence import BusinessIntelligenceAgent
from app.agents.campaign_strategist import CampaignStrategistAgent
from app.agents.competitor_intelligence import CompetitorIntelligenceAgent
from app.agents.copy_intelligence import CopyIntelligenceAgent

# -- V2 expansion: 21-25, 65 creative generation ---------------------------
from app.agents.creative_generation import (
    ContentAngleAgent,
    CreativeBriefAgent,
    HookEngineAgent,
    StaticCreativeConceptAgent,
    UGCStrategistAgent,
    VideoScriptAgent,
)
from app.agents.creative_intelligence import CreativeIntelligenceAgent

# -- V2 expansion: 26-30 creative operations -------------------------------
from app.agents.creative_ops import (
    ContentCalendarAgent,
    CreativeDiversityAgent,
    CreativeFatiguePredictionAgent,
    CreativeRefreshAgent,
    CreativeScoringAgent,
)

# -- V2 expansion: 17-20 customer intelligence -----------------------------
from app.agents.customer_intelligence import (
    BuyerAwarenessAgent,
    CustomerAvatarAgent,
    CustomerJourneyAgent,
    CustomerLanguageMiningAgent,
)
from app.agents.data_analyst import DataAnalystAgent

# -- V2 expansion: 39-43 data quality / statistics / trends / anomalies ----
from app.agents.data_quality import (
    AnomalyDetectionAgent,
    MarketConditionAgent,
    StatisticalAnalysisAgent,
    TimeSeriesTrendAgent,
    TrackingDataQualityAgent,
)
from app.agents.experimentation import ExperimentationAgent
from app.agents.forecasting import ForecastingAgent
from app.agents.funnel_diagnostics import FunnelDiagnosticsAgent

# -- V2 expansion: 49-54 funnel economics / scaling / recovery ------------
from app.agents.funnel_economics import (
    BudgetAllocationSimulatorAgent,
    FunnelEconomicsAgent,
    MarginalPerformanceAgent,
    RecoveryAgent,
    ScalingRiskAgent,
    StopPauseDecisionAgent,
)

# -- V2 expansion: 60-64 policy / brand safety / voice / content quality --
from app.agents.governance import (
    AdPolicyComplianceAgent,
    BrandSafetyAgent,
    BrandVoiceAgent,
    ContentQualityAgent,
    HumanLikeCopyEditorAgent,
)
from app.agents.guardian import GuardianAgent

# -- V2 expansion: 31-38 landing page, funnel, sales -----------------------
from app.agents.landing_funnel import (
    CRMIntelligenceAgent,
    FormOptimizationAgent,
    LandingPageCopyAgent,
    LandingPageCROAgent,
    LeadResponseAgent,
    LeadScoringAgent,
    SalesConversionAgent,
    SalesFeedbackLoopAgent,
)
from app.agents.lead_quality import LeadQualityAgent

# -- V2 expansion: 57-59, 69 learning / knowledge graph / library / opportunity
from app.agents.learning_intelligence import (
    CreativeLibraryManagerAgent,
    KnowledgeGraphAgent,
    LearningSynthesisAgent,
    OpportunityDiscoveryAgent,
)
from app.agents.offer_psychology import OfferPsychologyAgent
from app.agents.optimization import OptimizationAgent

# -- V2 expansion: 44-48 positioning / offer / objections / proof ---------
from app.agents.positioning_offer import (
    ObjectionMiningAgent,
    OfferCreativeMatchingAgent,
    OfferTestingAgent,
    PositioningAgent,
    SocialProofAgent,
)

# -- V2 expansion: 66-68, 70 prioritization / portfolio / strategy --------
from app.agents.prioritization import (
    CreativeProductionPrioritizerAgent,
    ExecutiveStrategyAgent,
    ExperimentPortfolioAgent,
    ExplorationExploitationAgent,
)

# -- V2 expansion: 55-56 post-change verification / rollback --------------
from app.agents.verification import PostChangeVerificationAgent, RollbackDecisionAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    # Tier 1/2 core
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
    # Customer intelligence (17-20)
    CustomerAvatarAgent.name: CustomerAvatarAgent,
    CustomerLanguageMiningAgent.name: CustomerLanguageMiningAgent,
    BuyerAwarenessAgent.name: BuyerAwarenessAgent,
    CustomerJourneyAgent.name: CustomerJourneyAgent,
    # Creative generation (21-25, 65)
    HookEngineAgent.name: HookEngineAgent,
    ContentAngleAgent.name: ContentAngleAgent,
    UGCStrategistAgent.name: UGCStrategistAgent,
    VideoScriptAgent.name: VideoScriptAgent,
    StaticCreativeConceptAgent.name: StaticCreativeConceptAgent,
    CreativeBriefAgent.name: CreativeBriefAgent,
    # Creative operations (26-30)
    CreativeFatiguePredictionAgent.name: CreativeFatiguePredictionAgent,
    CreativeRefreshAgent.name: CreativeRefreshAgent,
    CreativeScoringAgent.name: CreativeScoringAgent,
    CreativeDiversityAgent.name: CreativeDiversityAgent,
    ContentCalendarAgent.name: ContentCalendarAgent,
    # Landing page / funnel / sales (31-38)
    LandingPageCopyAgent.name: LandingPageCopyAgent,
    LandingPageCROAgent.name: LandingPageCROAgent,
    FormOptimizationAgent.name: FormOptimizationAgent,
    LeadResponseAgent.name: LeadResponseAgent,
    SalesConversionAgent.name: SalesConversionAgent,
    CRMIntelligenceAgent.name: CRMIntelligenceAgent,
    LeadScoringAgent.name: LeadScoringAgent,
    SalesFeedbackLoopAgent.name: SalesFeedbackLoopAgent,
    # Data quality / statistics / trends / anomalies / market (39-43)
    TrackingDataQualityAgent.name: TrackingDataQualityAgent,
    StatisticalAnalysisAgent.name: StatisticalAnalysisAgent,
    TimeSeriesTrendAgent.name: TimeSeriesTrendAgent,
    AnomalyDetectionAgent.name: AnomalyDetectionAgent,
    MarketConditionAgent.name: MarketConditionAgent,
    # Positioning / offer / objections / proof (44-48)
    PositioningAgent.name: PositioningAgent,
    OfferTestingAgent.name: OfferTestingAgent,
    ObjectionMiningAgent.name: ObjectionMiningAgent,
    SocialProofAgent.name: SocialProofAgent,
    OfferCreativeMatchingAgent.name: OfferCreativeMatchingAgent,
    # Funnel economics / scaling / recovery (49-54)
    FunnelEconomicsAgent.name: FunnelEconomicsAgent,
    MarginalPerformanceAgent.name: MarginalPerformanceAgent,
    ScalingRiskAgent.name: ScalingRiskAgent,
    BudgetAllocationSimulatorAgent.name: BudgetAllocationSimulatorAgent,
    StopPauseDecisionAgent.name: StopPauseDecisionAgent,
    RecoveryAgent.name: RecoveryAgent,
    # Verification / rollback (55-56)
    PostChangeVerificationAgent.name: PostChangeVerificationAgent,
    RollbackDecisionAgent.name: RollbackDecisionAgent,
    # Learning / knowledge graph / library / opportunity (57-59, 69)
    LearningSynthesisAgent.name: LearningSynthesisAgent,
    KnowledgeGraphAgent.name: KnowledgeGraphAgent,
    CreativeLibraryManagerAgent.name: CreativeLibraryManagerAgent,
    OpportunityDiscoveryAgent.name: OpportunityDiscoveryAgent,
    # Governance: policy / brand safety / voice / content quality (60-64)
    AdPolicyComplianceAgent.name: AdPolicyComplianceAgent,
    BrandSafetyAgent.name: BrandSafetyAgent,
    BrandVoiceAgent.name: BrandVoiceAgent,
    ContentQualityAgent.name: ContentQualityAgent,
    HumanLikeCopyEditorAgent.name: HumanLikeCopyEditorAgent,
    # Prioritization / portfolio / exploration / strategy (66-68, 70)
    CreativeProductionPrioritizerAgent.name: CreativeProductionPrioritizerAgent,
    ExperimentPortfolioAgent.name: ExperimentPortfolioAgent,
    ExplorationExploitationAgent.name: ExplorationExploitationAgent,
    ExecutiveStrategyAgent.name: ExecutiveStrategyAgent,
}
"""Guardian is intentionally excluded — it has a different (review) contract
and is invoked directly by the orchestrator after recommendations exist."""

assert len(AGENT_REGISTRY) == 69, f"Expected 69 registered agents (70 total incl. Guardian), got {len(AGENT_REGISTRY)}"

__all__ = ["AGENT_REGISTRY", "GuardianAgent", "BaseAgent"]
