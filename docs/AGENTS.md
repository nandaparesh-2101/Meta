# Agents

All agents live in `app/agents/`. 15 of them share `BaseAgent`
(`analyze(context) -> list[AgentFinding]`); Guardian has its own contract
(`review(context, recommendations) -> list[GuardianDecision]`).

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
| 09 | Funnel Diagnostics | `funnel_diagnostics.py` | Finds the single weakest funnel step and maps it to plausible root causes. |
| 10 | Experimentation | `experimentation.py` | Converts hypotheses into pre-registered experiments; blocks duplicates. |
| 11 | Budget & Scaling | `budget_scaling.py` | INCREASE / DECREASE / REALLOCATE / MAINTAIN, gated by `rules/scaling_rules.py`. |
| 12 | Forecasting | `forecasting.py` | Transparent trend-projection with explicit confidence/assumptions/data basis. |
| 13 | Attribution | `attribution.py` | Connects ads -> leads -> sales -> revenue; flags broken attribution chains. |
| 14 | Competitor Intelligence | `competitor_intelligence.py` | Only activates when `context.competitor_research` is supplied (no live research performed). |
| 15 | Optimization Decision | `optimization.py` | Converts findings into prioritized, structured `Recommendation`s; preserves agent disagreement. |
| 16 | Guardian | `guardian.py` | Reviews every recommendation for safety; has veto power (`REJECT`). |

## Routing table (which agents run for which problem)

Defined in `app/orchestration/router.py`. `business_intelligence` always
runs first; `experimentation` and `optimization` always run last (before
Guardian); everything in between is trigger-specific:

| Trigger | Diagnostic sequence |
|---------|---------------------|
| `cpl_increase` | data_analyst -> creative_intelligence -> audience_intelligence -> funnel_diagnostics -> lead_quality |
| `cheap_leads_poor_sales` | lead_quality -> funnel_diagnostics -> offer_psychology -> attribution |
| `ctr_decrease` | data_analyst -> creative_intelligence -> copy_intelligence -> audience_intelligence |
| `scaling_review` | data_analyst -> campaign_strategist -> budget_scaling -> forecasting |
| `creative_fatigue_check` | data_analyst -> creative_intelligence -> copy_intelligence |
| `funnel_investigation` | funnel_diagnostics -> lead_quality -> offer_psychology -> attribution |
| *(anything else)* | `scheduled_review`: data_analyst, campaign_strategist, audience_intelligence, creative_intelligence, lead_quality, funnel_diagnostics, budget_scaling, forecasting, attribution |

`competitor_intelligence` only runs when `AgentContext.competitor_research`
is non-empty for that call.

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
)
```

## Adding a new agent

1. Subclass `BaseAgent` in a new file under `app/agents/`.
2. Implement `analyze(self, context: AgentContext) -> list[AgentFinding]`.
3. Register it in `AGENT_REGISTRY` in `app/agents/__init__.py`.
4. Add it to the relevant route(s) in `app/orchestration/router.py`, or
   leave it out of every route and have the orchestrator invoke it
   conditionally (like `competitor_intelligence`).
5. Add scenario coverage in `tests/test_orchestrator_scenarios.py` if the
   new agent should change behavior on one of the 10 mock scenarios.
