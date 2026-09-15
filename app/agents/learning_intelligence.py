"""Agents 57-59 and 69 — Learning Synthesis, Knowledge Graph, Creative
Library Management, and Opportunity Discovery.

These agents operate on THIS run's findings (cross-agent synthesis) rather
than duplicating `app.memory.learnings`, which persists learnings ACROSS
runs from completed experiments. `LearningSynthesisAgent` here produces the
in-run strategic narrative; `app.memory.learnings.LearningMemory` is what
durably stores a learning once an experiment concludes.
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.ads import AudienceType
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext


class LearningSynthesisAgent(BaseAgent):
    name = "learning_synthesis"
    description = "Combines this run's cross-agent findings into higher-level strategic insights. Repeated evidence outweighs isolated results."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        sales_feedback = context.findings_by_agent("sales_feedback_loop")
        audience_findings = [f for f in context.findings_by_agent("audience_intelligence") if "audience_comparison" in f.tags]
        creative_pattern = [f for f in context.findings_by_agent("creative_intelligence") if "creative_pattern" in f.tags]

        supporting = []
        if sales_feedback and sales_feedback[0].payload.get("revenue_by_angle"):
            best_angle = max(sales_feedback[0].payload["revenue_by_angle"], key=sales_feedback[0].payload["revenue_by_angle"].get)
            supporting.append(f"'{best_angle}' angle leads actual sale revenue (sales_feedback_loop)")
        if audience_findings:
            supporting.append(audience_findings[0].headline + " (audience_intelligence)")
        if creative_pattern:
            supporting.append(creative_pattern[0].headline + " (creative_intelligence)")

        if not supporting:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="Not enough independent findings this run to synthesize a strategic pattern.",
                    detail="Strategic synthesis requires at least one revenue-attributed and one performance-pattern finding.",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0,
                    suggested_actions=[], tags=["no_synthesis_possible"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        # Repeated/independent evidence is stronger than an isolated result.
        confidence = min(0.3 + 0.15 * len(supporting), 0.75)

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Strategic pattern synthesized from {len(supporting)} independent finding(s).",
                detail=(
                    " + ".join(supporting)
                    + f" — combined, these point to a reusable pattern worth deliberately testing further "
                    f"({len(supporting)} independent signal(s) support it; treat as a hypothesis, not settled fact "
                    "until confirmed by a dedicated experiment)."
                ),
                evidence=supporting,
                data_sufficiency=DataSufficiencyLevel.PROMISING if len(supporting) >= 2 else DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=confidence,
                suggested_actions=[ActionType.LAUNCH_TEST],
                tags=["learning_synthesis"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                payload={"supporting_signal_count": len(supporting)},
            )
        ]


class KnowledgeGraphAgent(BaseAgent):
    name = "knowledge_graph"
    description = "Maintains explicit relationships: audience -> creative -> hook -> offer -> campaign -> lead quality -> sales -> revenue."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        edges = []
        for ad_set in context.ad_sets:
            edges.append({"from": ad_set.audience.audience_type.value, "relation": "targeted_by", "to": ad_set.ad_set_id})
            campaign = next((c for c in context.campaigns if c.campaign_id == ad_set.campaign_id), None)
            if campaign:
                edges.append({"from": ad_set.ad_set_id, "relation": "belongs_to", "to": campaign.campaign_id})

        for ad in context.ads:
            creative = context.creative_for_ad(ad.ad_id)
            edges.append({"from": ad.ad_id, "relation": "in_ad_set", "to": ad.ad_set_id})
            if creative:
                edges.append({"from": ad.ad_id, "relation": "uses_hook", "to": creative.hook})
                if creative.offer_stated:
                    edges.append({"from": ad.ad_id, "relation": "makes_offer", "to": creative.offer_stated})

        revenue_by_ad: dict[str, float] = defaultdict(float)
        for sale in context.sales:
            revenue_by_ad[sale.ad_id] += sale.amount
        for ad_id, revenue in revenue_by_ad.items():
            edges.append({"from": ad_id, "relation": "produced_revenue", "to": round(revenue, 2)})

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Knowledge graph built: {len(edges)} relationship edge(s) across audience/creative/hook/offer/campaign/sales.",
                detail="This graph is rebuilt from this run's data each time — persisting it across runs (for true long-term intelligence) belongs in the memory layer, not in a single agent's findings.",
                evidence=[f"{e['from']} --{e['relation']}--> {e['to']}" for e in edges[:15]],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT if edges else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.5,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["knowledge_graph"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"edge_count": len(edges), "edges": edges},
            )
        ]


class CreativeLibraryManagerAgent(BaseAgent):
    name = "creative_library_manager"
    description = "Catalogs the creative library with performance/fatigue status and flags near-duplicate hooks."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.creatives:
            return [
                AgentFinding(
                    agent_name=self.name, headline="No creatives in the library.", detail="", evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0, suggested_actions=[],
                    tags=["no_creative_data"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        fatigue_by_ad = {f.entity_id: f.payload.get("fatigue_level", "LOW") for f in context.findings_by_agent("creative_fatigue_prediction")}

        entries = []
        cpl_by_ad = {}
        for ad in context.ads:
            insights = context.insights_for_ad(ad.ad_id)
            if insights:
                cpl_by_ad[ad.ad_id] = MetricSnapshot.aggregate(insights).cpl
        ranked = sorted((aid for aid, cpl in cpl_by_ad.items() if cpl is not None), key=lambda aid: cpl_by_ad[aid])
        winners = set(ranked[: max(1, len(ranked) // 3)])
        losers = set(ranked[-max(1, len(ranked) // 3):]) if len(ranked) > 2 else set()

        seen_hook_prefixes: dict[str, str] = {}
        duplicates = []
        for creative in context.creatives:
            prefix = " ".join(creative.hook.lower().split()[:4])
            if prefix in seen_hook_prefixes and seen_hook_prefixes[prefix] != creative.ad_id:
                duplicates.append((creative.ad_id, seen_hook_prefixes[prefix]))
            else:
                seen_hook_prefixes[prefix] = creative.ad_id

            status = "winner" if creative.ad_id in winners else "loser" if creative.ad_id in losers else "in_progress"
            entries.append({
                "ad_id": creative.ad_id, "hook": creative.hook, "format": creative.format.value,
                "status": status, "fatigue": fatigue_by_ad.get(creative.ad_id, "LOW"), "is_active": creative.is_active,
            })

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Library: {len(entries)} creative(s) cataloged, {len(duplicates)} near-duplicate hook(s) flagged.",
                detail="Status classification uses CPL tercile ranking where calculable; fatigue pulled from CreativeFatiguePredictionAgent.",
                evidence=[f"{e['ad_id']}: {e['status']}/{e['fatigue']}" for e in entries],
                data_sufficiency=DataSufficiencyLevel.PROMISING,
                confidence=0.5,
                suggested_actions=[ActionType.DIVERSIFY_CREATIVE] if duplicates else [ActionType.DO_NOTHING],
                tags=["creative_library"] + (["duplicate_hooks_detected"] if duplicates else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"entries": entries, "duplicates": duplicates},
            )
        ]


class OpportunityDiscoveryAgent(BaseAgent):
    name = "opportunity_discovery"
    description = "Searches for overlooked opportunities: underfunded winners, untested audiences/angles, funnel gaps."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        opportunities = []

        # Underfunded winner: best-CPL campaign with below-median budget share.
        snapshots = {c.campaign_id: (c, MetricSnapshot.aggregate(context.insights_for_campaign(c.campaign_id))) for c in context.campaigns}
        eligible = {cid: (c, s) for cid, (c, s) in snapshots.items() if s.cpl}
        if len(eligible) >= 2:
            budgets = sorted(c.daily_budget for c, _ in eligible.values())
            median_budget = budgets[len(budgets) // 2]
            best_id = min(eligible, key=lambda cid: eligible[cid][1].cpl)
            if eligible[best_id][0].daily_budget <= median_budget:
                opportunities.append(f"Underfunded winner: {best_id} has the best CPL but below-median budget.")

        untested_angles = []
        angle_findings = context.findings_by_agent("content_angle")
        if angle_findings:
            untested_angles = angle_findings[0].payload.get("untested_angles", [])
            if untested_angles:
                opportunities.append(f"Untested angle(s) available: {untested_angles[:3]}")

        used_audience_types = {a.audience.audience_type.value for a in context.ad_sets}
        untested_audience_types = [t.value for t in AudienceType if t.value not in used_audience_types]
        if untested_audience_types:
            opportunities.append(f"Untested audience type(s): {untested_audience_types}")

        bottleneck_findings = context.findings_by_agent("funnel_economics")
        for f in bottleneck_findings:
            bottleneck_tag = next((t for t in f.tags if t.startswith("economic_bottleneck:")), None)
            if bottleneck_tag:
                opportunities.append(f"Funnel improvement opportunity in {f.entity_id}: {bottleneck_tag.split(':')[1]}")

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(opportunities)} overlooked opportunit(y/ies) surfaced this run.",
                detail="; ".join(opportunities) if opportunities else "No clear overlooked opportunity surfaced this run.",
                evidence=opportunities,
                data_sufficiency=DataSufficiencyLevel.PROMISING if opportunities else DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.45,
                suggested_actions=[ActionType.LAUNCH_TEST] if opportunities else [ActionType.DO_NOTHING],
                tags=["opportunity_discovery"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                payload={"opportunities": opportunities},
            )
        ]
