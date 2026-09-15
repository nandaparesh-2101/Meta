# Architecture

## Layered design

```
┌─────────────────────────────────────────────────────────────────┐
│ API (FastAPI)                    app/api/routes.py, app/main.py │
├─────────────────────────────────────────────────────────────────┤
│ Orchestration       Orchestrator, Router, AgentContext           │
│                     app/orchestration/*                          │
├─────────────────────────────────────────────────────────────────┤
│ Agents              70 total: 16 core + 54 V2 specialists +      │
│                     Guardian — app/agents/*, registry.py         │
├─────────────────────────────────────────────────────────────────┤
│ Domain rules        KPI eval, data sufficiency, scaling, safety  │
│                     app/rules/*                                  │
├─────────────────────────────────────────────────────────────────┤
│ Metric engine       Pure, defensive metric math                  │
│                     app/metrics/engine.py                        │
├─────────────────────────────────────────────────────────────────┤
│ Models              Pydantic domain models (typed everywhere)    │
│                     app/models/*                                 │
├─────────────────────────────────────────────────────────────────┤
│ Memory              SQLite-backed findings/recs/experiments/     │
│                     learnings/audit log — app/memory/*           │
├─────────────────────────────────────────────────────────────────┤
│ Integrations        MetaAdsProvider interface + Mock impl        │
│                     app/integrations/*                           │
├─────────────────────────────────────────────────────────────────┤
│ Execution           Approval -> Executor -> Rollback (disabled   │
│                     by default) — app/execution/*                │
├─────────────────────────────────────────────────────────────────┤
│ LLM                 LLMProvider interface + deterministic Mock   │
│                     app/llm/provider.py                          │
└─────────────────────────────────────────────────────────────────┘
```

Each layer only depends on the layers below it. Agents never call
`sqlite3` directly (they go through `MemoryStore`); the API never
constructs a `Recommendation` itself (it calls the `Orchestrator`); nothing
outside `app/integrations` knows Meta's data shape beyond the typed models
in `app/models`.

## Data flow for one orchestration run

1. Caller builds a `BusinessObjective` (business economics + KPI targets +
   constraints) and pulls raw ad data via a `MetaAdsProvider` (the mock
   implementation in this build).
2. Both are assembled into a single `AgentContext` — the one mutable object
   threaded through the whole run.
3. `Orchestrator.run(context)`:
   a. Records `ANALYSIS_STARTED` to the audit log.
   b. Loads prior experiments from memory (for dedup).
   c. Runs `business_intelligence` first, unconditionally.
   d. Runs the universal data-quality preflight — `tracking_data_quality`
      and `anomaly_detection` — before any diagnostic conclusion is drawn,
      regardless of trigger.
   e. Asks `router.route_for_trigger(context.trigger)` for the ordered
      diagnostic agent sequence relevant to this problem, and runs exactly
      those agents (not every agent — see `docs/AGENTS.md` for the routing
      table).
   f. Conditionally runs `competitor_intelligence` if external research was
      supplied.
   g. Runs `experimentation`, which scans findings tagged as testable
      hypotheses and proposes deduplicated experiments.
   h. Runs `optimization`, which converts every actionable finding across
      all agents into prioritized `Recommendation` objects — preserving
      disagreement between agents rather than silently picking one.
   i. Persists every recommendation to `MemoryStore`.
   j. Runs `GuardianAgent.review()` over every recommendation, producing a
      `GuardianDecision` (APPROVE / APPROVE_WITH_CAUTION /
      REQUIRE_HUMAN_APPROVAL / REJECT) for each; stores the decisions on
      `context.guardian_decisions`.
   k. Runs the capstone `executive_strategy` agent, which reads
      `context.recommendations` + `context.guardian_decisions` (nothing
      else — it performs no new analysis) and produces a NOW/NEXT/LATER
      plan, excluding anything Guardian rejected.
   l. Persists every finding produced this run (including the capstone's)
      to `MemoryStore`.
   m. Creates `ApprovalRequest` objects for anything Guardian did not
      reject and that itself requires approval.
   n. Records `ANALYSIS_COMPLETED`.
4. `app.reports.command_center.generate_report()` turns the finished
   `AgentContext` + Guardian decisions into the 18-section Command Center
   report (pure presentation — it computes nothing new).

## Why routing, not "call every agent"

Calling all 16 agents on every request is expensive, noisy, and produces
recommendations nobody asked about. `app/orchestration/router.py` maps a
`trigger` (e.g. `cpl_increase`, `cheap_leads_poor_sales`, `ctr_decrease`) to
the ordered diagnostic sequence actually relevant to that symptom. An
unrecognized trigger falls back to a general `scheduled_review` sequence —
still not literally every agent.

## Why agent disagreement is preserved, not resolved silently

`OptimizationAgent` groups findings by entity, and when multiple agents
suggest different actions for the same entity, it creates a
`Recommendation` for **each** distinct action rather than picking a winner,
and flags the resulting finding with `agent_disagreement`. Guardian then
reviews every one of them independently. Nothing is thrown away.

## Why Guardian is a separate contract, not another `BaseAgent`

Every other agent's contract is "context in, findings out." Guardian's job
is fundamentally different — it reviews already-produced recommendations
and has veto power — so `GuardianAgent` is a standalone class with a
`review(context, recommendations) -> list[GuardianDecision]` method rather
than forcing an artificial `analyze()` override. This keeps `BaseAgent`'s
contract honest for the 15 agents that really do share it.

## Data sufficiency is structural, not a suggestion

`DataSufficiencyLevel` (INSUFFICIENT_DATA / EARLY_SIGNAL / PROMISING /
CONFIDENT) is a required field on every `AgentFinding` and
`Recommendation`. `BaseAgent.run()` caps `confidence` against
`rules.data_sufficiency.confidence_ceiling()` for the reported sufficiency
level automatically — an agent cannot claim 0.9 confidence on two days of
data even if its own logic tries to.

## V2 expansion: how 54 new agents plug into the same architecture

The V2 agents (17-70) did not introduce a second architecture — they use
the same `BaseAgent` contract, the same `AGENT_REGISTRY`/router pattern,
and the same memory/Guardian/reporting pipeline as the original 16.
Three additions were made, deliberately minimal:

1. **Richer `AgentFinding` fields** (`status`, `evidence_sources`,
   `assumptions`, `questions`, `payload`) — additive, not a breaking
   change; every V1 agent's findings still validate. `payload` is the one
   new mechanism worth understanding: agents that need to pass a
   structured sub-object downstream (e.g. `CustomerAvatarAgent`'s
   `CustomerAvatarProfile`, `HookEngineAgent`'s generated hook list) put it
   in `finding.payload`, and downstream agents read it via
   `context.findings_by_agent("customer_avatar")[0].payload["avatar"]` —
   the same finding-passing pattern `ExperimentationAgent` already used in
   V1 (reading tags off prior findings), just generalized to carry
   structured data instead of only strings.
2. **A handful of new `AgentContext` fields**, all optional and empty/None
   by default in mock mode: `customer_language_sources`, `crm_records`,
   `brand_voice`, `baseline_insights`, plus the orchestrator-populated
   `guardian_decisions`. `brand_voice` is the one field an agent
   (`BrandVoiceAgent`) writes directly rather than only reading — a
   deliberate, documented exception, since a "reusable voice profile other
   agents must respect" is inherently a piece of run-scoped shared state,
   not a per-entity finding.
3. **Two orchestrator hooks**: a universal preflight (data quality/anomaly
   checks that should gate every kind of analysis, not just one trigger)
   and a capstone (executive strategy, which needs to see the *final*
   Guardian-cleared recommendation set and therefore cannot be a normal
   routed diagnostic agent).

No V1 agent was rewritten to accommodate V2 — `CreativeFatiguePredictionAgent`
(26) exists alongside `CreativeIntelligenceAgent` (05)'s existing single-ad
fatigue signal rather than replacing it, because they answer different
questions (05: "does this ad show CTR/frequency decline?" vs. 26: "how many
independent fatigue signals does this ad show, gated to avoid a one-metric
false positive?"). Where a V2 agent's job was truly a superset of a V1
agent's, the V2 agent explicitly says so and reads the V1 agent's findings
rather than recomputing them (e.g. `RecoveryAgent` reads `data_analyst` /
`creative_fatigue_prediction` / `audience_intelligence` tags instead of
re-deriving trend data).
