"""Agents 17-20 — Customer Intelligence.

Builds the customer-understanding layer that the creative generation
pipeline (agents 21-25, 65) consumes: who the customer is, in what words
they describe their problem, how aware they are of the solution, and where
they are in the buying journey.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.avatar import (
    AWARENESS_MESSAGING_STRUCTURE,
    BuyerAwarenessLevel,
    CustomerAvatarProfile,
)
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext

# -- 18: naive-but-real language extraction (no fabrication: only substrings
# actually present in supplied text are ever returned) --------------------
OBJECTION_MARKERS = ["expensive", "afford", "not sure", "worried", "risk", "trust", "too much", "don't know"]
DESIRE_MARKERS = ["want", "wish", "hope", "need", "looking for", "finally"]
EMOTION_MARKERS = ["frustrated", "excited", "relieved", "nervous", "confident", "overwhelmed"]


class CustomerAvatarAgent(BaseAgent):
    name = "customer_avatar"
    description = "Builds a customer avatar profile, separating observed, inferred, and hypothesized facts."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        profile = context.business_objective.profile
        observed: dict[str, list[str]] = {"demographics": [profile.target_customer, f"Geography: {profile.geography}"]}
        inferred: dict[str, list[str]] = {}
        hypothesized: dict[str, list[str]] = {}

        pains = sorted({c.problem_stated for c in context.creatives if c.problem_stated})
        desires = sorted({c.desire_stated for c in context.creatives if c.desire_stated})
        if pains:
            inferred["pain_points"] = pains
        if desires:
            inferred["desired_outcomes"] = desires
        if context.customer_language_sources:
            observed["raw_customer_language"] = list(context.customer_language_sources)

        kpis = context.business_objective.kpis
        if profile.price > 0:
            ratio = kpis.target_cpl / profile.price
            sensitivity = "high" if ratio > 0.2 else "moderate" if ratio > 0.08 else "low"
            hypothesized["price_sensitivity"] = [
                f"Estimated {sensitivity} price sensitivity (target CPL is {ratio:.0%} of price) — "
                "an economic inference, not a directly observed customer fact."
            ]

        confidence = 0.55 if context.customer_language_sources else 0.3
        sufficiency = (
            DataSufficiencyLevel.PROMISING if context.customer_language_sources else DataSufficiencyLevel.EARLY_SIGNAL
        )

        avatar = CustomerAvatarProfile(
            observed=observed, inferred=inferred, hypothesized=hypothesized, confidence=confidence
        )

        sources = [EvidenceSource.USER_INPUT, EvidenceSource.MODEL_INFERENCE]
        if context.customer_language_sources:
            sources.append(EvidenceSource.EXTERNAL_RESEARCH)

        return [
            AgentFinding(
                agent_name=self.name,
                headline="Customer avatar profile assembled — observed/inferred/hypothesized kept separate.",
                detail=(
                    f"Observed: {list(observed)}. Inferred: {list(inferred)}. Hypothesized: {list(hypothesized)}. "
                    "Dimensions with no supporting data are absent, never backfilled with a guess."
                ),
                evidence=[f"{k}: {v}" for k, v in {**observed, **inferred}.items()],
                data_sufficiency=sufficiency,
                confidence=confidence,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["customer_avatar"],
                status=FindingStatus.COMPLETE,
                evidence_sources=sources,
                assumptions=[v for vs in hypothesized.values() for v in vs],
                questions=(
                    [] if context.customer_language_sources
                    else ["No customer language source (reviews/transcripts/support notes) was supplied — "
                          "avatar is currently built from business intake + existing ad copy only."]
                ),
                payload={"avatar": avatar.model_dump(mode="json")},
            )
        ]


class CustomerLanguageMiningAgent(BaseAgent):
    name = "customer_language_mining"
    description = "Extracts real problem/desire/objection/emotional language from supplied customer text."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        sources = context.customer_language_sources
        if not sources:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No customer language sources supplied — nothing to mine.",
                    detail=(
                        "This agent only extracts language actually present in supplied reviews/testimonials/"
                        "transcripts/support notes. None were provided this run; it will not fabricate quotes."
                    ),
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_customer_language_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                    questions=["Supply customer_language_sources (reviews, transcripts, support notes) to activate this agent."],
                )
            ]

        objections, desires, emotions = [], [], []
        for snippet in sources:
            lower = snippet.lower()
            if any(marker in lower for marker in OBJECTION_MARKERS):
                objections.append(snippet)
            if any(marker in lower for marker in DESIRE_MARKERS):
                desires.append(snippet)
            if any(marker in lower for marker in EMOTION_MARKERS):
                emotions.append(snippet)

        sufficiency = DataSufficiencyLevel.PROMISING if len(sources) >= 10 else DataSufficiencyLevel.EARLY_SIGNAL

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Mined {len(sources)} customer language sample(s): {len(objections)} objection-flagged, {len(desires)} desire-flagged.",
                detail=(
                    "Every quote below is verbatim from a supplied source — nothing was generated or paraphrased. "
                    "Use these as raw material for hooks/copy, not as statistically representative of all customers."
                ),
                evidence=[f"Objection language: {q}" for q in objections[:5]]
                + [f"Desire language: {q}" for q in desires[:5]]
                + [f"Emotional language: {q}" for q in emotions[:5]],
                data_sufficiency=sufficiency,
                confidence=0.5 if sufficiency == DataSufficiencyLevel.PROMISING else 0.3,
                suggested_actions=[ActionType.ADJUST_COPY] if (objections or desires) else [ActionType.DO_NOTHING],
                tags=["customer_language"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.EXTERNAL_RESEARCH],
                payload={
                    "objection_language": objections,
                    "desire_language": desires,
                    "emotional_language": emotions,
                },
            )
        ]


class BuyerAwarenessAgent(BaseAgent):
    name = "buyer_awareness"
    description = "Classifies the audience's awareness level and recommends the matching message structure."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        # Heuristic: infer awareness from what the existing creative library
        # already assumes (offer-forward copy implies a more-aware audience;
        # problem-first copy implies a less-aware one) plus audience type mix.
        offer_forward = sum(1 for c in context.creatives if c.offer_stated and not c.problem_stated)
        problem_forward = sum(1 for c in context.creatives if c.problem_stated)
        retargeting_adsets = sum(1 for a in context.ad_sets if a.audience.audience_type.value == "retargeting")

        if retargeting_adsets and offer_forward >= problem_forward:
            level = BuyerAwarenessLevel.MOST_AWARE
        elif offer_forward > problem_forward:
            level = BuyerAwarenessLevel.PRODUCT_AWARE
        elif problem_forward > 0:
            level = BuyerAwarenessLevel.PROBLEM_AWARE
        else:
            level = BuyerAwarenessLevel.UNAWARE

        structure = AWARENESS_MESSAGING_STRUCTURE[level]
        confidence = 0.45 if (context.creatives or retargeting_adsets) else 0.15

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Primary audience classified as '{level.value}' based on existing creative/audience mix.",
                detail=(
                    f"Recommended message structure for this awareness level: {' -> '.join(structure)}. "
                    "This is inferred from what the account's own creative already assumes, not from a direct "
                    "survey of the audience — treat as a working hypothesis for new creative, not settled fact."
                ),
                evidence=[
                    f"{offer_forward} offer-forward creative(s), {problem_forward} problem-forward creative(s), "
                    f"{retargeting_adsets} retargeting ad set(s)",
                ],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=confidence,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["buyer_awareness"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                assumptions=[f"Awareness level inferred as '{level.value}' from existing creative composition."],
                payload={"awareness_level": level.value, "message_structure": structure},
            )
        ]


class CustomerJourneyAgent(BaseAgent):
    name = "customer_journey"
    description = "Maps Awareness -> Consideration -> Intent -> Conversion -> Retention -> Referral messaging needs."

    STAGES = ["awareness", "consideration", "intent", "conversion", "retention", "referral"]

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        has_retargeting = any(a.audience.audience_type.value == "retargeting" for a in context.ad_sets)
        has_prospecting = any(a.audience.audience_type.value in ("broad", "interest", "lookalike") for a in context.ad_sets)
        has_post_sale_signal = bool(context.sales)

        coverage = {
            "awareness": has_prospecting,
            "consideration": has_prospecting,
            "intent": has_retargeting,
            "conversion": has_retargeting or bool(context.leads),
            "retention": False,  # no post-sale/retention ad sets are modeled in this build
            "retention_signal_available": has_post_sale_signal,
            "referral": False,
        }
        gaps = [stage for stage in ("retention", "referral") if not coverage.get(stage)]

        recommendations = {
            "prospecting_messaging": "Awareness/consideration: lead with problem or curiosity, not the offer.",
            "retargeting_messaging": "Intent/conversion: lead with proof and a clear, low-friction offer.",
            "conversion_messaging": "Remove friction — restate the offer and answer the top objection.",
            "retention_messaging": (
                "No retention campaign structure detected in this account — customer lifecycle "
                "value is being left on the table if repeat/referral messaging isn't run elsewhere."
            ),
        }

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"Journey coverage: prospecting {'present' if has_prospecting else 'MISSING'}, "
                    f"retargeting {'present' if has_retargeting else 'MISSING'}, retention/referral not modeled."
                ),
                detail=(
                    "Stage-by-stage messaging recommendations below. Retention and referral stages have no "
                    "corresponding ad set type in this system yet — flagged as a structural gap, not a performance issue."
                ),
                evidence=[f"{stage}: {'covered' if v else 'gap'}" for stage, v in coverage.items() if isinstance(v, bool)],
                data_sufficiency=DataSufficiencyLevel.PROMISING if context.ad_sets else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.5,
                suggested_actions=[ActionType.DO_NOTHING] if not gaps else [ActionType.LAUNCH_TEST],
                tags=["customer_journey"] + ([f"journey_gap:{g}" for g in gaps]),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"stage_coverage": coverage, "recommendations": recommendations},
            )
        ]
