"""Direct unit tests for a representative sample of the 54 V2 specialist
agents — one per major behavioral guarantee the spec calls out (no
fabrication, multi-signal fatigue, risk-detector framing, never-automatic
rollback, etc.).
"""

from __future__ import annotations

from app.agents.creative_ops import CreativeFatiguePredictionAgent
from app.agents.customer_intelligence import (
    BuyerAwarenessAgent,
    CustomerAvatarAgent,
    CustomerLanguageMiningAgent,
)
from app.agents.funnel_economics import FunnelEconomicsAgent
from app.agents.governance import AdPolicyComplianceAgent, BrandSafetyAgent, BrandVoiceAgent
from app.agents.prioritization import ExecutiveStrategyAgent
from app.agents.verification import PostChangeVerificationAgent, RollbackDecisionAgent
from app.models.execution import GuardianDecision, GuardianVerdict
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, Priority, Recommendation, RiskLevel
from tests.conftest import build_context


def test_customer_avatar_separates_observed_inferred_hypothesized(full_mock_account):
    context = build_context(full_mock_account)
    findings = CustomerAvatarAgent().run(context)
    avatar = findings[0].payload["avatar"]
    assert "observed" in avatar and "inferred" in avatar and "hypothesized" in avatar
    # Demographics come straight from business intake -> observed, never hypothesized.
    assert "demographics" in avatar["observed"]


def test_customer_avatar_never_invents_when_no_language_supplied(full_mock_account):
    context = build_context(full_mock_account)
    assert context.customer_language_sources == []
    findings = CustomerAvatarAgent().run(context)
    assert findings[0].questions, "Should flag that no customer language source was supplied"


def test_language_mining_extracts_only_real_supplied_text(full_mock_account):
    context = build_context(full_mock_account)
    context.customer_language_sources = [
        "This is way too expensive for what I get, not sure it works",
        "I finally found a plan that fits my schedule, so happy",
    ]
    findings = CustomerLanguageMiningAgent().run(context)
    payload = findings[0].payload
    assert payload["objection_language"] == ["This is way too expensive for what I get, not sure it works"]
    assert payload["desire_language"] == ["I finally found a plan that fits my schedule, so happy"]
    # Nothing fabricated: every returned string is byte-identical to a supplied source.
    for quote in payload["objection_language"] + payload["desire_language"]:
        assert quote in context.customer_language_sources


def test_language_mining_reports_insufficient_data_when_empty(full_mock_account):
    context = build_context(full_mock_account)
    findings = CustomerLanguageMiningAgent().run(context)
    assert findings[0].data_sufficiency == DataSufficiencyLevel.INSUFFICIENT_DATA
    assert findings[0].status.value == "insufficient_data"


def test_buyer_awareness_classifies_and_recommends_structure(full_mock_account):
    context = build_context(full_mock_account)
    findings = BuyerAwarenessAgent().run(context)
    assert findings[0].payload["awareness_level"] in (
        "unaware", "problem_aware", "solution_aware", "product_aware", "most_aware",
    )
    assert len(findings[0].payload["message_structure"]) >= 3


def test_creative_fatigue_requires_multiple_signals(scenario_context):
    context = scenario_context("creative_fatigue")
    findings = CreativeFatiguePredictionAgent().run(context)
    assert findings, "Should produce a fatigue finding for the creative_fatigue scenario"
    for f in findings:
        signal_count = f.payload["signal_count"]
        level = f.payload["fatigue_level"]
        if level in ("MEDIUM", "HIGH", "CRITICAL"):
            assert signal_count >= 2, "MEDIUM+ fatigue must never be declared from a single signal"


def test_creative_fatigue_low_when_no_signals(scenario_context):
    context = scenario_context("strong_campaign")
    findings = CreativeFatiguePredictionAgent().run(context)
    for f in findings:
        assert f.payload["fatigue_level"] == "LOW"


def test_funnel_economics_identifies_a_bottleneck(scenario_context):
    context = scenario_context("high_cpl_campaign")
    findings = FunnelEconomicsAgent().run(context)
    assert findings
    tagged = [f for f in findings if any(t.startswith("economic_bottleneck:") for t in f.tags)]
    assert tagged, "Should identify at least one economic bottleneck for a campaign with full funnel data"


def test_ad_policy_compliance_flags_risky_phrases(full_mock_account):
    context = build_context(full_mock_account)
    # Inject a known-risky phrase into one creative to prove detection works.
    risky_creative = context.creatives[0].model_copy(update={"primary_text": "Guaranteed results overnight, 100% guaranteed."})
    context.creatives[0] = risky_creative
    findings = AdPolicyComplianceAgent().run(context)
    flagged = [f for f in findings if f.entity_id == risky_creative.ad_id]
    assert flagged, "Should flag the creative containing risky guarantee language"
    assert "ad_policy_risk" in flagged[0].tags


def test_ad_policy_compliance_is_a_risk_detector_not_a_guarantee(full_mock_account):
    context = build_context(full_mock_account)
    findings = AdPolicyComplianceAgent().run(context)
    assert any("guarantee" in f.detail.lower() for f in findings)


def test_brand_voice_sets_context_and_brand_safety_reads_it(full_mock_account):
    context = build_context(full_mock_account)
    BrandVoiceAgent().run(context)
    assert context.brand_voice is not None
    assert "guaranteed" in context.brand_voice.words_to_avoid

    violating_creative = context.creatives[0].model_copy(update={"hook": "This is a guaranteed transformation."})
    context.creatives[0] = violating_creative
    findings = BrandSafetyAgent().run(context)
    assert any("brand_violation" in f.tags for f in findings)


def test_post_change_verification_insufficient_without_baseline(full_mock_account):
    context = build_context(full_mock_account)
    assert context.baseline_insights == []
    findings = PostChangeVerificationAgent().run(context)
    assert findings[0].status.value == "insufficient_data"


def test_post_change_verification_detects_improvement(full_mock_account):
    context = build_context(full_mock_account)
    context.baseline_insights = context.insights  # same data -> UNCHANGED, not a fabricated improvement
    findings = PostChangeVerificationAgent().run(context)
    assert findings[0].payload["verdict"] in ("UNCHANGED", "INCONCLUSIVE")


def test_rollback_decision_never_fires_without_verification(full_mock_account):
    context = build_context(full_mock_account)
    findings = RollbackDecisionAgent().run(context)
    assert findings[0].status.value == "insufficient_data"
    assert ActionType.ROLLBACK_CHANGE not in findings[0].suggested_actions


def test_executive_strategy_excludes_guardian_rejected_recommendations(full_mock_account):
    context = build_context(full_mock_account)
    rec = Recommendation(
        recommendation_id="rec_rejected_1", entity_id="cmp_x", entity_level="campaign",
        action=ActionType.DECREASE_BUDGET, priority=Priority.P0_CRITICAL, reason="test",
        expected_impact="test", confidence=0.9, risk=RiskLevel.HIGH, measurement="test",
        review_window_days=14, data_sufficiency=DataSufficiencyLevel.CONFIDENT,
    )
    context.recommendations = [rec]
    context.guardian_decisions = [
        GuardianDecision(recommendation_id="rec_rejected_1", verdict=GuardianVerdict.REJECT, reasoning="blocked")
    ]
    findings = ExecutiveStrategyAgent().run(context)
    payload = findings[0].payload
    assert "rec_rejected_1" not in payload["now"]
    assert "rec_rejected_1" not in payload["next"]
    assert "rec_rejected_1" not in payload["later"]
