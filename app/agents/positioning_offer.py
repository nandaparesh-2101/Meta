"""Agents 44-48 — Positioning, Offer, Objection, Social Proof, Offer-Creative Matching.

`OfferPsychologyAgent` (agent 07) already detects *whether* the offer is
likely the root cause of a performance gap. These agents go further: they
design offer experiments, mine objections into usable content, catalog
legitimate proof, and match offers to the creative angle/format that best
communicates them.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext

OFFER_TEST_LEVERS = ["price", "bundles", "bonuses", "guarantees", "trials", "discounts", "financing", "scarcity", "value_framing"]

COMMON_OBJECTIONS = {
    "too_expensive": ["expensive", "afford", "cost", "price"],
    "not_sure_it_works": ["not sure it works", "does it work", "skeptical"],
    "trust": ["trust", "scam", "legit"],
    "timing": ["not now", "later", "timing"],
    "complexity": ["complicated", "complex", "hard to"],
    "competitor_comparison": ["vs", "compared to", "better than"],
    "risk": ["risk", "guarantee", "refund"],
}


class PositioningAgent(BaseAgent):
    name = "positioning"
    description = "Analyzes UVP/differentiation and recommends positioning opportunities."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        profile = context.business_objective.profile
        proof_elements = sorted({p for c in context.creatives for p in c.proof_elements})
        offers = sorted({c.offer_stated for c in context.creatives if c.offer_stated})
        differentiators = proof_elements + offers

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"{len(differentiators)} differentiation signal(s) currently in market (proof + offer claims)."
                    if differentiators else "No explicit differentiation signals found in current creative — positioning is undefined in the ad copy."
                ),
                detail=(
                    f"Business: {profile.business_type} serving {profile.target_customer} in {profile.geography}. "
                    "Recommend testing whether leading with a specific differentiator (not just the category) "
                    "improves relevance over generic category messaging."
                ),
                evidence=differentiators,
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.35,
                suggested_actions=[ActionType.DO_NOTHING] if differentiators else [ActionType.LAUNCH_TEST],
                tags=["positioning"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.USER_INPUT],
                payload={"differentiators": differentiators},
            )
        ]


class OfferTestingAgent(BaseAgent):
    name = "offer_testing"
    description = "Designs offer experiments (price/bundle/bonus/guarantee/trial/discount/financing/scarcity/framing)."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        profile = context.business_objective.profile
        kpis = context.business_objective.kpis

        candidates = []
        if profile.gross_margin_pct >= 0.4:
            candidates.append(("guarantees", "Margin supports a stronger guarantee (e.g. money-back) without threatening unit economics."))
        if kpis.target_cac < profile.average_customer_lifetime_value * 0.3:
            candidates.append(("trials", "Healthy LTV:CAC room to test a free/discounted trial period."))
        candidates.append(("value_framing", "Test reframing price as a per-day/per-use cost vs. a lump sum."))

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(candidates)} offer experiment lever(s) worth testing, given current business economics.",
                detail="; ".join(f"{lever}: {reason}" for lever, reason in candidates),
                evidence=[f"margin={profile.gross_margin_pct:.0%}, LTV={profile.average_customer_lifetime_value:.2f}, target_CAC={kpis.target_cac:.2f}"],
                data_sufficiency=DataSufficiencyLevel.PROMISING,
                confidence=0.45,
                suggested_actions=[ActionType.LAUNCH_TEST],
                tags=["offer_testing"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.USER_INPUT, EvidenceSource.MODEL_INFERENCE],
                payload={"candidate_levers": [lever for lever, _ in candidates], "all_levers": OFFER_TEST_LEVERS},
            )
        ]


class ObjectionMiningAgent(BaseAgent):
    name = "objection_mining"
    description = "Identifies common objections and converts them into ad/FAQ/landing-page/sales content."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        found: dict[str, list[str]] = {}
        for snippet in context.customer_language_sources:
            lower = snippet.lower()
            for objection, markers in COMMON_OBJECTIONS.items():
                if any(m in lower for m in markers):
                    found.setdefault(objection, []).append(snippet)

        if not found:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No customer language supplied to mine for objections.",
                    detail="Standard objection categories tracked, but none can be confirmed from real customer language this run.",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_objection_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                    payload={"tracked_categories": list(COMMON_OBJECTIONS)},
                )
            ]

        conversions = {
            objection: {
                "faq_entry": f"Address '{objection.replace('_', ' ')}' directly in the FAQ.",
                "objection_hook": f"\"{quotes[0]}\" — here's the real answer.",
            }
            for objection, quotes in found.items()
        }

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(found)} objection categor(ies) confirmed in supplied customer language: {list(found)}",
                detail="Each confirmed objection includes a suggested FAQ entry and objection-hook starting point.",
                evidence=[f"{k}: {v[:2]}" for k, v in found.items()],
                data_sufficiency=DataSufficiencyLevel.PROMISING if len(context.customer_language_sources) >= 10 else DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.5,
                suggested_actions=[ActionType.ADJUST_COPY, ActionType.ADJUST_LANDING_PAGE],
                tags=["objection_mining"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.EXTERNAL_RESEARCH],
                payload={"objections": found, "conversions": conversions},
            )
        ]


class SocialProofAgent(BaseAgent):
    name = "social_proof"
    description = "Catalogs legitimate proof elements on file and recommends where they should appear. Never fabricates proof."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        proof_by_creative = {c.ad_id: c.proof_elements for c in context.creatives if c.proof_elements}
        total_proof = sum(len(v) for v in proof_by_creative.values())
        creatives_without_proof = [c.ad_id for c in context.creatives if not c.proof_elements]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{total_proof} legitimate proof element(s) on file across {len(proof_by_creative)} creative(s); {len(creatives_without_proof)} creative(s) have none.",
                detail=(
                    "Recommend surfacing existing proof (never fabricated) in: hook (for high-skepticism angles), "
                    "landing page hero/near-CTA, and objection-response content. Creatives without proof are the "
                    "highest-priority candidates to add a real testimonial/stat once one becomes available."
                ),
                evidence=[f"{ad_id}: {elements}" for ad_id, elements in proof_by_creative.items()],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT if context.creatives else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.6,
                suggested_actions=[ActionType.ADJUST_COPY] if creatives_without_proof else [ActionType.DO_NOTHING],
                tags=["social_proof"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"creatives_without_proof": creatives_without_proof},
            )
        ]


class OfferCreativeMatchingAgent(BaseAgent):
    name = "offer_creative_matching"
    description = "Determines which creative angle/format best communicates a given offer, for a given audience."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        matches = []
        for creative in context.creatives:
            if not creative.offer_stated:
                continue
            ad = next((a for a in context.ads if a.creative_id == creative.creative_id), None)
            ad_set = next((s for s in context.ad_sets if ad and s.ad_set_id == ad.ad_set_id), None)
            matches.append({
                "offer": creative.offer_stated,
                "audience": ad_set.audience.audience_type.value if ad_set else "unknown",
                "angle": creative.emotional_angle,
                "hook": creative.hook,
                "format": creative.format.value,
                "cta": creative.cta,
            })

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(matches)} offer-to-creative mapping(s) cataloged.",
                detail="Use this mapping to check whether the same offer is being tested across multiple angles/formats, or is stuck with only one execution.",
                evidence=[f"{m['offer']} -> {m['angle']}/{m['format']} for {m['audience']}" for m in matches],
                data_sufficiency=DataSufficiencyLevel.PROMISING if matches else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.4,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["offer_creative_matching"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"matches": matches},
            )
        ]
