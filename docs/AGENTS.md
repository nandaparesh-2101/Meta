# Agents

70 agents total: 16 core (agents 01-16, including Guardian) plus a V2
expansion of 54 advanced specialists (agents 17-70). All of them share
`BaseAgent` (`analyze(context) -> list[AgentFinding]`) except Guardian,
whose contract is `review(context, recommendations) -> list[GuardianDecision]`.

For the full machine-readable catalog (tier, capabilities, inputs, outputs,
dependencies, priority, enabled status) see `app/agents/registry.py`'s
`AGENT_CATALOG`. `app/agents/__init__.py`'s `AGENT_REGISTRY` is what the
orchestrator actually instantiates from — the two are validated to match
exactly (`tests/test_agent_registry_v2.py`).

## Core 16 (agents 01-16)

| # | Agent | Module | Purpose |
|---|-------|--------|---------|
| 01 | Business Intelligence | `business_intelligence.py` | Sanity-checks and summarizes the business objective/KPI/constraints every other agent reasons against. |
| 02 | Data Analyst | `data_analyst.py` | Trends, winners/losers, anomalies, missing data — never invents a missing value. |
| 03 | Campaign Strategist | `campaign_strategist.py` | Structure: fragmentation, consolidation vs. testing structure. |
| 04 | Audience Intelligence | `audience_intelligence.py` | Saturation/fatigue via frequency; compares audience types without assuming narrow beats broad. |
| 05 | Creative Intelligence | `creative_intelligence.py` | Creative fatigue detection; patterns behind top-performing creatives. |
| 06 | Copy Intelligence | `copy_intelligence.py` | Generates hypothesis-driven copy test variations for weak-CTR ads. |
| 07 | Offer & Psychology | `offer_psychology.py` | Detects when strong top-funnel + weak bottom-funnel points at the offer, not the ad. |
| 08 | Lead Quality | `lead_quality.py` | Full funnel walk; flags cheap-but-low-quality lead patterns. |
| 09 | Funnel Diagnostics | `funnel_diagnostics.py` | Finds the single weakest ad-to-lead funnel step and maps it to plausible root causes. |
| 10 | Experimentation | `experimentation.py` | Converts hypotheses into pre-registered experiments; blocks duplicates. |
| 11 | Budget & Scaling | `budget_scaling.py` | INCREASE / DECREASE / REALLOCATE / MAINTAIN, gated by `rules/scaling_rules.py`. |
| 12 | Forecasting | `forecasting.py` | Transparent trend-projection with explicit confidence/assumptions/data basis. |
| 13 | Attribution | `attribution.py` | Connects ads -> leads -> sales -> revenue; flags broken attribution chains. |
| 14 | Competitor Intelligence | `competitor_intelligence.py` | Only activates when `context.competitor_research` is supplied (no live research performed). |
| 15 | Optimization Decision | `optimization.py` | Converts findings into prioritized, structured `Recommendation`s; preserves agent disagreement. |
| 16 | Guardian | `guardian.py` | Reviews every recommendation for safety; has veto power (`REJECT`). |

## V2 expansion (agents 17-70)

| # | Agent | Module | Purpose |
|---|-------|--------|---------|
| 17 | Customer Avatar | `customer_intelligence.py` | Builds an observed/inferred/hypothesized customer avatar profile — never invents customer facts. |
| 18 | Customer Language Mining | `customer_intelligence.py` | Extracts real objection/desire/emotion language from supplied customer text only. |
| 19 | Buyer Awareness | `customer_intelligence.py` | Classifies unaware -> most-aware and recommends the matching message structure. |
| 20 | Customer Journey | `customer_intelligence.py` | Maps awareness->consideration->intent->conversion->retention->referral coverage/gaps. |
| 21 | Hook Engine | `creative_generation.py` | Generates/evaluates hooks across 11 angle categories, each with an explicit hypothesis. |
| 22 | Content Angle | `creative_generation.py` | Structured creative angle library; tracks which angles are already tested. |
| 23 | UGC Strategist | `creative_generation.py` | UGC concepts (HOOK->PROBLEM->EXPERIENCE->SOLUTION->PROOF->CTA); never fabricates testimonials. |
| 24 | Video Script | `creative_generation.py` | Duration-scaled (15-90s) video scripts with beats, on-screen text, B-roll. |
| 25 | Static Creative Concept | `creative_generation.py` | Static/carousel/infographic/comparison concepts. |
| 26 | Creative Fatigue Prediction | `creative_ops.py` | Multi-signal LOW/MEDIUM/HIGH/CRITICAL fatigue classification — never from one metric alone. |
| 27 | Creative Refresh | `creative_ops.py` | For HIGH/CRITICAL fatigue: preserves the winning pattern, varies execution only. |
| 28 | Creative Scoring | `creative_ops.py` | 10-dimension prioritization score — explicitly not a performance guarantee. |
| 29 | Creative Diversity | `creative_ops.py` | Flags overused hook/angle/format patterns; recommends diversification. |
| 30 | Content Calendar | `creative_ops.py` | Structured weekly production plan; tracks created/tested/winner/loser/needs-refresh. |
| 31 | Landing Page Copy | `landing_funnel.py` | Ad-to-landing-page message-match check + copy checklist (no page-content model exists yet). |
| 32 | Landing Page CRO | `landing_funnel.py` | Diagnoses landing page conversion problems from real click/LP-view/lead data. |
| 33 | Form Optimization | `landing_funnel.py` | Balances form conversion rate vs. downstream lead quality — never optimizes blindly. |
| 34 | Lead Response | `landing_funnel.py` | Response time / contact rate — checks whether sales, not ads, is the bottleneck. |
| 35 | Sales Conversion | `landing_funnel.py` | Contact->Qualified->Appointment->Sale bottleneck — never blames Meta for sales-side issues. |
| 36 | CRM Intelligence | `landing_funnel.py` | Connects ad source to CRM lead/sale/revenue status, when CRM data is supplied. |
| 37 | Lead Scoring | `landing_funnel.py` | Explainable per-campaign lead-quality score (intent + engagement components shown). |
| 38 | Sales Feedback Loop | `landing_funnel.py` | Feeds sale revenue back to the originating creative angle — closes the loop. |
| 39 | Tracking & Data Quality | `data_quality.py` | Duplicate lead IDs, out-of-order timestamps, missing data — runs as a universal preflight. |
| 40 | Statistical Analysis | `data_quality.py` | Sample-size caution pass (1/sqrt(n) rule of thumb) over trend findings. |
| 41 | Time-Series Trend | `data_quality.py` | Gradual deterioration vs. sudden-change detection in daily CPL. |
| 42 | Anomaly Detection | `data_quality.py` | z-score pass across spend/leads/CPL/CTR/CPM/CPC — runs as a universal preflight. |
| 43 | Market Condition | `data_quality.py` | External market/seasonality context — only when research was actually supplied. |
| 44 | Positioning | `positioning_offer.py` | UVP/differentiation analysis. |
| 45 | Offer Testing | `positioning_offer.py` | Designs price/bundle/bonus/guarantee/trial/discount experiments. |
| 46 | Objection Mining | `positioning_offer.py` | Mines real objections into FAQ/ad/landing-page content. |
| 47 | Social Proof | `positioning_offer.py` | Catalogs legitimate proof; never fabricates it. |
| 48 | Offer-Creative Matching | `positioning_offer.py` | Maps offer -> audience -> angle -> hook -> format -> CTA. |
| 49 | Funnel Economics | `funnel_economics.py` | Full-funnel $ economics; identifies the single highest-cost bottleneck. |
| 50 | Marginal Performance | `funnel_economics.py` | High- vs. low-spend-day comparison as a marginal-cost proxy. |
| 51 | Scaling Risk | `funnel_economics.py` | SAFE / CAUTION / HIGH_RISK verdict combining audience/creative/funnel/sales signals. |
| 52 | Budget Allocation Simulator | `funnel_economics.py` | Simulates reallocation scenarios — explicitly labeled forecast, not fact. |
| 53 | Stop/Pause Decision | `funnel_economics.py` | Determines whether pausing is defensible — avoids premature pausing. |
| 54 | Recovery | `funnel_economics.py` | WHAT/WHEN/WHERE/WHY diagnosis + recovery plan after significant deterioration. |
| 55 | Post-Change Verification | `verification.py` | Before vs. after: IMPROVED/UNCHANGED/WORSE/INCONCLUSIVE, from real baseline data only. |
| 56 | Rollback Decision | `verification.py` | Determines whether rollback should be considered — never automatic. |
| 57 | Learning Synthesis | `learning_intelligence.py` | Combines this run's cross-agent findings into strategic patterns; repeated evidence > isolated results. |
| 58 | Knowledge Graph | `learning_intelligence.py` | Audience->creative->hook->offer->campaign->sales relationship graph. |
| 59 | Creative Library Manager | `learning_intelligence.py` | Catalogs the library with performance/fatigue status; flags near-duplicate hooks. |
| 60 | Ad Policy & Compliance | `governance.py` | Flags policy-risk language — a risk detector, not an approval guarantee. |
| 61 | Brand Safety | `governance.py` | Checks creative against the brand voice's words-to-avoid; flags contradictions. |
| 62 | Brand Voice | `governance.py` | Maintains the reusable brand voice profile every content agent must respect. |
| 63 | Content Quality | `governance.py` | Rejects hype/generic AI-generated content missing specificity. |
| 64 | Human-like Copy Editor | `governance.py` | Deterministic hype-word cleanup — NOT an LLM rewrite (none is connected). |
| 65 | Creative Brief | `creative_generation.py` | Assembles a complete production-ready brief from every upstream finding. |
| 66 | Creative Production Prioritizer | `prioritization.py` | Ranks generated concepts into a production queue. |
| 67 | Experiment Portfolio | `prioritization.py` | Prevents too many simultaneous tests running at once. |
| 68 | Exploration vs. Exploitation | `prioritization.py` | Balances scaling winners against testing new; flags creative concentration risk. |
| 69 | Opportunity Discovery | `learning_intelligence.py` | Underfunded winners, untested audiences/angles, funnel improvement opportunities. |
| 70 | Executive Strategy | `prioritization.py` | Synthesizes Guardian-cleared recommendations into a NOW/NEXT/LATER plan. Runs last, always. |

## Tiers

See `app/agents/registry.py` (`Tier` enum) for the authoritative mapping.
Summary: **T0 control** (Guardian) · **T1 business intelligence**
(attribution, lead quality, funnel economics, sales conversion) · **T2
performance** (data analyst, anomaly/trend/statistics, scaling risk,
recovery, verification) · **T3 creative** (fatigue/refresh/scoring/
diversity, hook engine + generation) · **T4 content** (copy, language
mining, brand voice, content quality, editor, brief) · **T5 funnel**
(landing page, CRO, form, lead response, CRM, sales feedback) · **T6
experimentation** (experimentation, portfolio, exploration/exploitation,
offer testing) · **T7 intelligence** (competitor, positioning, journey,
knowledge graph, learning synthesis, opportunity discovery, policy/brand
safety, optimization, executive strategy).

## Routing table (which agents run for which problem)

Defined in `app/orchestration/router.py`. Every run follows this fixed
shape:

```
business_intelligence (always first)
  -> tracking_data_quality, anomaly_detection (universal preflight)
  -> [trigger-specific route from ROUTES]
  -> competitor_intelligence (conditional: only if research supplied)
  -> experimentation -> optimization -> guardian
  -> executive_strategy (capstone, always last)
```

| Trigger | Diagnostic sequence |
|---------|---------------------|
| `cpl_increase` | data_analyst -> creative_intelligence -> audience_intelligence -> funnel_diagnostics -> lead_quality |
| `cheap_leads_poor_sales` | lead_quality -> funnel_diagnostics -> offer_psychology -> attribution |
| `ctr_decrease` | data_analyst -> creative_intelligence -> copy_intelligence -> audience_intelligence |
| `scaling_review` | data_analyst -> campaign_strategist -> budget_scaling -> forecasting |
| `creative_fatigue_check` | data_analyst -> creative_intelligence -> copy_intelligence |
| `funnel_investigation` | funnel_diagnostics -> lead_quality -> offer_psychology -> attribution |
| `creative_performance_problem` | data_analyst -> creative_intelligence -> creative_fatigue_prediction -> creative_scoring -> content_quality -> creative_refresh |
| `lead_quality_problem` | lead_quality -> crm_intelligence -> sales_conversion -> sales_feedback_loop -> funnel_economics -> attribution |
| `content_creation_request` | customer_avatar -> customer_language_mining -> buyer_awareness -> customer_journey -> offer_psychology -> creative_intelligence -> content_angle -> hook_engine -> creative_brief -> ugc_strategist -> video_script -> static_creative_concept -> copy_intelligence -> brand_voice -> content_quality -> human_like_copy_editor -> ad_policy_compliance -> brand_safety |
| `scaling_request` | data_analyst -> marginal_performance -> budget_scaling -> scaling_risk -> funnel_economics -> forecasting |
| `sales_process_review` | lead_response -> sales_conversion -> crm_intelligence -> lead_scoring -> sales_feedback_loop |
| `offer_experiment_request` | offer_psychology -> positioning -> objection_mining -> social_proof -> offer_testing -> offer_creative_matching |
| `post_change_review` | post_change_verification -> rollback_decision |
| `portfolio_review` | experiment_portfolio -> exploration_exploitation -> opportunity_discovery -> creative_production_prioritizer -> learning_synthesis -> knowledge_graph |
| *(anything else)* | `scheduled_review`: the broadest periodic health-check route — data_analyst, statistical_analysis, time_series_trend, campaign_strategist, audience_intelligence, creative_intelligence, creative_fatigue_prediction, creative_scoring, creative_diversity, content_calendar, creative_library_manager, lead_quality, funnel_diagnostics, landing_page_copy, landing_page_cro, form_optimization, funnel_economics, budget_scaling, scaling_risk, budget_allocation_simulator, stop_pause_decision, recovery, forecasting, attribution, market_condition |

`competitor_intelligence` only runs when `AgentContext.competitor_research`
is non-empty. `tests/test_agent_registry_v2.py::test_every_registered_agent_is_reachable_by_routing`
enforces that every one of the 69 instantiable agents appears in at least
one route (or the always-first/preflight/always-last lists) — none are
dead code.

## Contract every finding must satisfy

```python
AgentFinding(
    agent_name=...,
    entity_id=...,           # campaign/ad_set/ad id, or None for account-level
    headline=...,            # one sentence
    detail=...,              # full reasoning
    evidence=[...],          # concrete numbers/observations, never assertions alone
    data_sufficiency=...,    # INSUFFICIENT_DATA | EARLY_SIGNAL | PROMISING | CONFIDENT
    confidence=...,          # 0.0-1.0, capped by data_sufficiency automatically
    suggested_actions=[...], # ActionType values, or [DO_NOTHING]
    tags=[...],              # e.g. "creative_fatigue", "tracking_anomaly"
    status=...,              # complete | insufficient_data | error (V2)
    evidence_sources=[...],  # META_DATA | CRM_DATA | USER_INPUT | EXPERIMENT_HISTORY | EXTERNAL_RESEARCH | MODEL_INFERENCE (V2)
    assumptions=[...],       # explicitly labeled inferences, not observed fact (V2)
    questions=[...],         # open questions the finding could not resolve (V2)
    payload={...},           # structured sub-output (e.g. a serialized CustomerAvatarProfile) (V2)
)
```

`BaseAgent.structured_output(context)` aggregates one agent's findings into
the flatter `{agent, status, findings, evidence, assumptions, confidence,
recommendations, questions}` contract from the V2 spec, for callers that
want that shape instead of `list[AgentFinding]`.

## Adding a new agent

1. Subclass `BaseAgent` in a new (or existing, if topically related) file
   under `app/agents/`.
2. Implement `analyze(self, context: AgentContext) -> list[AgentFinding]`.
3. Register it in `AGENT_REGISTRY` in `app/agents/__init__.py`.
4. Add a matching entry to `AGENT_CATALOG` in `app/agents/registry.py`
   (tier, capabilities, dependencies, priority).
5. Add it to the relevant route(s) in `app/orchestration/router.py`, or
   leave it conditional (like `competitor_intelligence`) or always-run
   (like the preflight/capstone agents in `workflow.py`).
6. Add scenario coverage in `tests/test_orchestrator_scenarios.py` (core
   scenarios) and/or a dedicated test file if the new agent introduces a
   new behavioral guarantee.
7. Run `pytest -q -k test_agent_registry_v2` to confirm the catalog,
   registry, and routing stay consistent.
