"""Agents 21-25 and 65 — Creative Generation.

Every agent here is a MOCK/deterministic generator: no LLM is connected in
this build, so content is assembled from real inputs already present in
`AgentContext` (business profile, avatar findings, mined customer language,
existing creative angles) via structured templates — never invented facts,
never a fabricated customer quote. Each generated piece states its own
hypothesis so it can be tested, per the "no uncontrolled experimentation"
rule enforced elsewhere in this system.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext


def _grounding(context: AgentContext) -> dict:
    """Pulls whatever real grounding material is available this run:
    avatar pains/desires, mined objection/desire language, and the
    product/audience facts every business always supplies."""
    profile = context.business_objective.profile
    avatar_findings = context.findings_by_agent("customer_avatar")
    language_findings = context.findings_by_agent("customer_language_mining")
    awareness_findings = context.findings_by_agent("buyer_awareness")

    pains: list[str] = []
    desires: list[str] = []
    objections: list[str] = []
    if avatar_findings:
        avatar_payload = avatar_findings[0].payload.get("avatar", {})
        pains += avatar_payload.get("inferred", {}).get("pain_points", [])
        desires += avatar_payload.get("inferred", {}).get("desired_outcomes", [])
    if language_findings:
        lang_payload = language_findings[0].payload
        objections += lang_payload.get("objection_language", [])
        desires += lang_payload.get("desire_language", [])

    proof_elements = sorted({p for c in context.creatives for p in c.proof_elements})
    awareness_level = awareness_findings[0].payload.get("awareness_level") if awareness_findings else None

    return {
        "product": profile.product_or_service,
        "customer": profile.target_customer,
        "pains": pains or [f"achieving results without {profile.product_or_service.lower()}"],
        "desires": desires or ["a faster, more reliable path to their goal"],
        "objections": objections,
        "proof": proof_elements,
        "awareness_level": awareness_level,
        "grounded": bool(pains or desires or objections or proof_elements),
    }


class HookEngineAgent(BaseAgent):
    name = "hook_engine"
    description = "Generates and evaluates hooks across proven angle categories, each with an explicit hypothesis."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        g = _grounding(context)
        product, customer = g["product"], g["customer"]
        pain = g["pains"][0]
        desire = g["desires"][0]

        hooks = [
            {"angle": "problem", "trigger": "pain recognition", "hook": f"Still struggling with {pain}?"},
            {"angle": "curiosity", "trigger": "curiosity gap", "hook": f"The one thing {customer} get wrong about {product}."},
            {"angle": "contrarian", "trigger": "pattern interrupt", "hook": f"Why more {product} isn't the answer."},
            {"angle": "benefit", "trigger": "outcome desire", "hook": f"Get {desire} — without the usual trade-offs."},
            {"angle": "story", "trigger": "identification", "hook": f"I used to deal with {pain}. Here's what changed."},
            {"angle": "authority", "trigger": "credibility", "hook": f"What actually works for {pain}, according to people who've solved it."},
            {"angle": "proof", "trigger": "social proof", "hook": (g["proof"][0] if g["proof"] else f"Real results from real {customer}.")},
            {"angle": "question", "trigger": "self-relevance", "hook": f"Is {pain} costing you more than you think?"},
            {"angle": "pattern_interrupt", "trigger": "novelty", "hook": f"Stop doing this if you want {desire}."},
            {"angle": "objection", "trigger": "objection pre-emption", "hook": (
                f"\"{g['objections'][0]}\" — here's the honest answer." if g["objections"]
                else f"Worried {product} won't work for you? Read this first."
            )},
            {"angle": "transformation", "trigger": "before/after identification", "hook": f"From {pain} to {desire}."},
        ]

        for h in hooks:
            h["audience"] = customer
            h["hypothesis"] = f"A '{h['angle']}' hook leveraging {h['trigger']} will out-perform generic copy for {customer}."

        sufficiency = DataSufficiencyLevel.EARLY_SIGNAL if g["grounded"] else DataSufficiencyLevel.INSUFFICIENT_DATA

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Generated {len(hooks)} hook candidates across {len(hooks)} distinct angles.",
                detail=(
                    "Each hook is grounded in real business/avatar/language data where available "
                    f"({'grounded in mined customer language/avatar data' if g['grounded'] else 'grounded only in business intake — no avatar/language data was available this run'}). "
                    "Every hook carries its own testable hypothesis; none should be shipped without a review pass "
                    "through Content Quality and the Human-like Copy Editor."
                ),
                evidence=[f"[{h['angle']}] {h['hook']}" for h in hooks],
                data_sufficiency=sufficiency,
                confidence=0.5 if g["grounded"] else 0.25,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["hook_engine", "generated_content"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE]
                + ([EvidenceSource.EXTERNAL_RESEARCH] if g["objections"] else []),
                questions=[] if g["grounded"] else ["No avatar or customer-language data available — hooks are generic to the business profile only."],
                payload={"hooks": hooks},
            )
        ]


CONTENT_ANGLES = [
    "problem", "solution", "transformation", "demonstration", "comparison", "myth_busting",
    "social_proof", "case_study", "objection", "faq", "educational", "emotional",
    "authority", "before_after", "mistake", "checklist", "story",
]


class ContentAngleAgent(BaseAgent):
    name = "content_angle"
    description = "Maintains a structured creative angle library and tracks which angles have been tested."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        tested_angles = sorted({c.emotional_angle for c in context.creatives})
        untested = [a for a in CONTENT_ANGLES if a not in tested_angles]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(tested_angles)}/{len(CONTENT_ANGLES)} angle categories represented in the current creative library.",
                detail=(
                    f"Tested/present angles: {', '.join(tested_angles) or 'none'}. "
                    f"Untested angles worth exploring: {', '.join(untested[:6])}."
                ),
                evidence=[f"Angle library: {CONTENT_ANGLES}"],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT if context.creatives else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.6,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT] if untested else [ActionType.DO_NOTHING],
                tags=["content_angle_library"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"tested_angles": tested_angles, "untested_angles": untested, "full_library": CONTENT_ANGLES},
            )
        ]


UGC_FORMATS = ["talking_head", "testimonial", "founder_video", "customer_story", "problem_solution", "demonstration", "review_style"]


class UGCStrategistAgent(BaseAgent):
    name = "ugc_strategist"
    description = "Designs UGC concepts (HOOK -> PROBLEM -> EXPERIENCE -> SOLUTION -> PROOF -> CTA)."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        g = _grounding(context)
        concepts = []
        for fmt in UGC_FORMATS[:4]:
            concepts.append({
                "format": fmt,
                "hook": f"I almost didn't try {g['product']} because of {g['pains'][0]}.",
                "problem": g["pains"][0],
                "experience": f"What it was actually like using {g['product']} to address that.",
                "solution": f"How {g['product']} specifically solved it.",
                "proof": (g["proof"][0] if g["proof"] else "INSUFFICIENT EVIDENCE — no proof element supplied; do not fabricate a testimonial."),
                "cta": "Learn more / Get started",
            })

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Drafted {len(concepts)} UGC concept(s) across {len(concepts)} format(s).",
                detail=(
                    "Every concept follows HOOK -> PROBLEM -> EXPERIENCE -> SOLUTION -> PROOF -> CTA. "
                    "No testimonial content is fabricated — the proof field is explicitly marked "
                    "'INSUFFICIENT EVIDENCE' when no real proof element is on file, and a real customer "
                    "must supply the actual experience/proof before this is produced as a real ad."
                ),
                evidence=[f"[{c['format']}] {c['hook']}" for c in concepts],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.4,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["ugc_concept", "generated_content"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                questions=["Real customer interviews/footage are required before any of these concepts can be produced — these are structural scripts, not sourced stories."],
                payload={"concepts": concepts},
            )
        ]


class VideoScriptAgent(BaseAgent):
    name = "video_script"
    description = "Generates performance-oriented video scripts for standard durations, with testing variations."

    DURATIONS = [15, 30, 45, 60, 90]

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        g = _grounding(context)
        scripts = []
        for duration in self.DURATIONS:
            beats = ["Opening hook (0-3s)"]
            if duration >= 30:
                beats.append("Problem framing")
            if duration >= 45:
                beats.append("Solution walkthrough / demonstration")
            if duration >= 60:
                beats.append("Proof / social proof")
            beats.append("CTA")
            scripts.append({
                "duration_sec": duration,
                "opening_hook": f"Still dealing with {g['pains'][0]}?",
                "beats": beats,
                "on_screen_text": [f"{g['pains'][0]}?", f"Try {g['product']}", "CTA: Get started"],
                "b_roll_suggestions": [f"{g['product']} in use", "Customer reaction shots", "Close-up on result/outcome"],
                "cta": "Get started today",
            })

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Drafted video scripts for {len(scripts)} duration(s): {', '.join(str(s['duration_sec']) + 's' for s in scripts)}.",
                detail="Each script scales its beat structure to duration; all should be treated as a starting brief for production, not a final shot list.",
                evidence=[f"{s['duration_sec']}s: {' -> '.join(s['beats'])}" for s in scripts],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.4,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["video_script", "generated_content"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                payload={"scripts": scripts},
            )
        ]


class StaticCreativeConceptAgent(BaseAgent):
    name = "static_creative_concept"
    description = "Generates concepts for static ads, carousels, infographics, and comparison/before-after designs."

    FORMATS = ["single_image", "carousel", "infographic", "before_after", "testimonial_design", "comparison"]

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        g = _grounding(context)
        concepts = [
            {
                "format": fmt,
                "concept": f"{fmt.replace('_', ' ').title()} built around: {g['pains'][0]} -> {g['desires'][0]}",
                "headline": f"{g['desires'][0].capitalize()} starts here",
                "visual_idea": f"Clear visual contrast/demonstration relevant to {g['product']}",
                "supporting_copy": f"For {g['customer']} dealing with {g['pains'][0]}.",
                "cta": "Learn more",
                "hypothesis": f"A {fmt.replace('_', ' ')} format will clarify the offer faster than long-form video for this audience.",
            }
            for fmt in self.FORMATS
        ]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Drafted {len(concepts)} static creative concept(s) across {len(concepts)} format(s).",
                detail="Each concept includes a testable hypothesis; none are ready to publish without creative/brand review.",
                evidence=[f"[{c['format']}] {c['headline']}" for c in concepts],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.4,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["static_creative_concept", "generated_content"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                payload={"concepts": concepts},
            )
        ]


class CreativeBriefAgent(BaseAgent):
    name = "creative_brief"
    description = "Assembles a complete creative brief before production, synthesizing all upstream inputs."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        g = _grounding(context)
        hook_findings = context.findings_by_agent("hook_engine")
        angle_findings = context.findings_by_agent("content_angle")

        top_hook = None
        if hook_findings and hook_findings[0].payload.get("hooks"):
            top_hook = hook_findings[0].payload["hooks"][0]
        top_angle = angle_findings[0].payload.get("untested_angles", ["problem"])[0] if angle_findings else "problem"

        brief = {
            "objective": context.business_objective.summary,
            "audience": g["customer"],
            "problem": g["pains"][0],
            "insight": f"{g['customer']} want {g['desires'][0]} but are held back by {g['pains'][0]}.",
            "angle": top_angle,
            "hook": top_hook["hook"] if top_hook else f"Still dealing with {g['pains'][0]}?",
            "offer": "See current offer in business objective / creative library",
            "proof": g["proof"] or ["INSUFFICIENT EVIDENCE — no proof element on file"],
            "format": "single_video",
            "cta": "Get started",
            "hypothesis": f"A {top_angle}-angle creative addressing '{g['pains'][0]}' will improve CTR/qualified CPL vs. current library average.",
            "success_metric": "CTR and qualified CPL vs. account average",
        }

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Creative brief assembled: {top_angle} angle targeting '{g['pains'][0]}'.",
                detail="Synthesizes avatar, language mining, awareness, and angle-library findings into one production-ready brief.",
                evidence=[f"{k}: {v}" for k, v in brief.items()],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL if g["grounded"] else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.45,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["creative_brief"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                payload={"brief": brief},
            )
        ]
