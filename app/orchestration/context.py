"""Shared workflow context.

A single `AgentContext` instance is threaded through one orchestration run.
It is the one place agents read ad-account data from and write findings to —
agents never reach into each other directly, which keeps them independently
testable and lets the orchestrator control execution order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.ads import Ad, AdSet, Campaign, Creative
from app.models.business import BusinessObjective
from app.models.experiments import Experiment
from app.models.leads import Lead, Sale
from app.models.metrics import DailyInsight
from app.models.recommendations import AgentFinding, Recommendation


@dataclass
class AgentContext:
    """Mutable, single-run context object.

    Populated up front from the (mock) Meta data provider + business intake,
    then progressively enriched with findings as each agent runs.
    """

    business_objective: BusinessObjective

    campaigns: list[Campaign] = field(default_factory=list)
    ad_sets: list[AdSet] = field(default_factory=list)
    ads: list[Ad] = field(default_factory=list)
    creatives: list[Creative] = field(default_factory=list)
    insights: list[DailyInsight] = field(default_factory=list)
    leads: list[Lead] = field(default_factory=list)
    sales: list[Sale] = field(default_factory=list)

    analysis_window_start: date | None = None
    analysis_window_end: date | None = None

    trigger: str = "manual"
    """What prompted this run, e.g. 'cpl_increase', 'scheduled_review'."""

    findings: list[AgentFinding] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    existing_experiments: list[Experiment] = field(default_factory=list)
    new_experiments: list[Experiment] = field(
        default_factory=list, metadata={"doc": "Experiments proposed by the Experimentation agent this run."}
    )
    competitor_research: list[str] = field(
        default_factory=list,
        metadata={"doc": "Optional externally-supplied research snippets. Empty in mock mode."},
    )

    def add_finding(self, finding: AgentFinding) -> None:
        self.findings.append(finding)

    def findings_by_agent(self, agent_name: str) -> list[AgentFinding]:
        return [f for f in self.findings if f.agent_name == agent_name]

    def findings_for_entity(self, entity_id: str) -> list[AgentFinding]:
        return [f for f in self.findings if f.entity_id == entity_id]

    def insights_for_campaign(self, campaign_id: str) -> list[DailyInsight]:
        return [i for i in self.insights if i.campaign_id == campaign_id]

    def insights_for_ad_set(self, ad_set_id: str) -> list[DailyInsight]:
        return [i for i in self.insights if i.ad_set_id == ad_set_id]

    def insights_for_ad(self, ad_id: str) -> list[DailyInsight]:
        return [i for i in self.insights if i.ad_id == ad_id]

    def creative_for_ad(self, ad_id: str) -> Creative | None:
        ad = next((a for a in self.ads if a.ad_id == ad_id), None)
        if ad is None:
            return None
        return next((c for c in self.creatives if c.creative_id == ad.creative_id), None)

    def leads_for_ad(self, ad_id: str) -> list[Lead]:
        return [lead for lead in self.leads if lead.ad_id == ad_id]

    def total_days_of_data(self) -> int:
        return len({i.date for i in self.insights})
