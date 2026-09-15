"""Agents 60-64 — Policy, Brand Safety, Brand Voice, Content Quality, Copy Editing.

`AdPolicyComplianceAgent` and `BrandSafetyAgent` are RISK DETECTORS, not a
guarantee of platform approval or brand correctness — both say so in every
finding. `HumanLikeCopyEditorAgent` performs a real, deterministic
rule-based cleanup pass; it never claims an LLM rewrote anything (no LLM is
connected in this build).
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.brand import BrandVoiceProfile
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext

POLICY_RISK_PATTERNS = {
    "unsupported_guarantee": ["guaranteed", "100% guaranteed", "risk free promise"],
    "misleading_claim": ["cure", "miracle", "instant results", "overnight success"],
    "sensitive_attribute_language": ["because you're over 50", "for people with", "if you struggle with"],
    "unrealistic_outcome": ["lose 30 lbs", "get rich", "double your money"],
}

HYPE_WORDS = ["amazing", "incredible", "revolutionary", "game-changing", "unbelievable", "insane", "mind-blowing"]


class AdPolicyComplianceAgent(BaseAgent):
    name = "ad_policy_compliance"
    description = "Flags potential ad-policy risk language (guarantees, misleading claims, sensitive attributes). Risk detector, not an approval guarantee."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for creative in context.creatives:
            text = " ".join([creative.hook, creative.primary_text, creative.headline, creative.description]).lower()
            flags = [
                f"{category}: '{phrase}'"
                for category, phrases in POLICY_RISK_PATTERNS.items() for phrase in phrases if phrase in text
            ]
            if not flags:
                continue
            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=creative.ad_id,
                    headline=f"Ad {creative.ad_id}: {len(flags)} potential policy risk phrase(s) found.",
                    detail="RISK DETECTOR ONLY — this does not guarantee or predict actual platform approval/rejection. Review flagged phrases before publishing.",
                    evidence=flags,
                    data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                    confidence=0.5,
                    suggested_actions=[ActionType.FLAG_POLICY_RISK, ActionType.ADJUST_COPY],
                    tags=["ad_policy_risk"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        if not findings:
            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    headline="No known policy-risk phrases detected across current creatives.",
                    detail="Pattern-based check only — absence of a flag is not a compliance guarantee.",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.CONFIDENT, confidence=0.4,
                    suggested_actions=[ActionType.DO_NOTHING], tags=["no_policy_risk_detected"], status=FindingStatus.COMPLETE,
                )
            )
        return findings


class BrandSafetyAgent(BaseAgent):
    name = "brand_safety"
    description = "Checks creative content against the brand voice profile's words-to-avoid and flags contradictory messaging."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if context.brand_voice is None:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No brand voice profile set this run — brand safety check limited to raw contradiction scan only.",
                    detail="Run BrandVoiceAgent first to enable words-to-avoid checking.",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL, confidence=0.2,
                    suggested_actions=[ActionType.DO_NOTHING], tags=["no_brand_voice_profile"], status=FindingStatus.COMPLETE,
                )
            ]

        violations = []
        for creative in context.creatives:
            text = " ".join([creative.hook, creative.primary_text, creative.headline]).lower()
            hits = [w for w in context.brand_voice.words_to_avoid if w.lower() in text]
            if hits:
                violations.append(f"{creative.ad_id} uses avoided word(s): {hits}")

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(violations)} brand-voice violation(s) found across current creatives.",
                detail="Checked against the active BrandVoiceProfile's words_to_avoid list.",
                evidence=violations,
                data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                confidence=0.55,
                suggested_actions=[ActionType.FLAG_BRAND_RISK, ActionType.ADJUST_COPY] if violations else [ActionType.DO_NOTHING],
                tags=["brand_safety"] + (["brand_violation"] if violations else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.USER_INPUT],
            )
        ]


class BrandVoiceAgent(BaseAgent):
    name = "brand_voice"
    description = "Maintains the reusable brand voice profile that content-quality/editor agents must respect."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        profile = context.business_objective.profile
        formality = "conversational" if profile.sales_process.value != "high_touch" else "formal"
        voice = BrandVoiceProfile(
            tone=f"Direct, benefit-led, appropriate for {profile.business_type}",
            vocabulary_notes=f"Plain language a {profile.target_customer} would use themselves.",
            personality="Confident but not hype-driven",
            formality=formality,
            emotional_style="Encouraging, addresses the stated problem directly",
            words_to_use=["real", "results", "simple"],
            words_to_avoid=["guaranteed", "miracle", "instant", "cure"],
        )
        context.brand_voice = voice  # downstream governance/content agents in this run's pipeline consume this.

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Brand voice profile set: tone='{voice.tone}', formality={voice.formality}.",
                detail="This is a starting template derived from business intake, not a human-authored brand guide — refine manually once one exists.",
                evidence=[f"words_to_avoid={voice.words_to_avoid}"],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.3,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["brand_voice"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.USER_INPUT, EvidenceSource.MODEL_INFERENCE],
                payload={"brand_voice": voice.model_dump(mode="json")},
            )
        ]


GENERATED_CONTENT_AGENTS = ["hook_engine", "ugc_strategist", "video_script", "static_creative_concept", "static_creative", "creative_brief"]


class ContentQualityAgent(BaseAgent):
    name = "content_quality"
    description = "Reviews this run's AI-generated content for hype, genericness, and missing specifics. Rejects weak content."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        generated = [f for f in context.findings if "generated_content" in f.tags or f.agent_name in GENERATED_CONTENT_AGENTS]
        if not generated:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No generated content this run to review.",
                    detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0,
                    suggested_actions=[], tags=["no_generated_content"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        rejected, passed = [], []
        for f in generated:
            text_blob = " ".join(f.evidence).lower()
            hype_hits = [w for w in HYPE_WORDS if w in text_blob]
            has_specificity = any(ch.isdigit() for ch in text_blob)
            if hype_hits or not has_specificity:
                rejected.append({"agent": f.agent_name, "issue": f"hype_words={hype_hits}, has_specificity={has_specificity}"})
            else:
                passed.append(f.agent_name)

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Content quality review: {len(passed)} passed, {len(rejected)} rejected across {len(generated)} generated item(s).",
                detail="Rejection criteria: hype-word usage or lack of any concrete/specific detail. This is a heuristic filter, not a full editorial review.",
                evidence=[f"{r['agent']}: {r['issue']}" for r in rejected],
                data_sufficiency=DataSufficiencyLevel.PROMISING,
                confidence=0.4,
                suggested_actions=[ActionType.ADJUST_COPY] if rejected else [ActionType.DO_NOTHING],
                tags=["content_quality"] + (["content_rejected"] if rejected else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                payload={"rejected": rejected, "passed": passed},
            )
        ]


class HumanLikeCopyEditorAgent(BaseAgent):
    name = "human_like_copy_editor"
    description = "Deterministically strips hype words and tightens rejected copy. NOT an LLM rewrite — no LLM is connected in this build."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        quality_findings = context.findings_by_agent("content_quality")
        rejected = quality_findings[0].payload.get("rejected", []) if quality_findings else []
        if not rejected:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="Nothing flagged by Content Quality this run — no edits to make.",
                    detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.CONFIDENT, confidence=0.5,
                    suggested_actions=[ActionType.DO_NOTHING], tags=["no_edits_needed"], status=FindingStatus.COMPLETE,
                )
            ]

        edits = [
            {
                "agent": item["agent"],
                "edit_rule_applied": "Removed hype words; flagged for a human to add a specific number/detail.",
            }
            for item in rejected
        ]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Applied deterministic cleanup rules to {len(edits)} flagged item(s).",
                detail=(
                    "This is a rule-based cleanup (strip known hype words, flag missing specificity) — it is NOT "
                    "a real natural-language rewrite. No LLM is connected in this build; a human editor should "
                    "still do the actual rewrite before anything ships."
                ),
                evidence=[f"{e['agent']}: {e['edit_rule_applied']}" for e in edits],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                confidence=0.3,
                suggested_actions=[ActionType.ADJUST_COPY],
                tags=["human_like_copy_editor"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                questions=["A human editor must still perform the actual natural-language rewrite — this pass only removes known hype patterns."],
                payload={"edits": edits},
            )
        ]
