# Architecture

## Layered design

```
┌─────────────────────────────────────────────────────────────────┐
│ API (FastAPI)                    app/api/routes.py, app/main.py │
├─────────────────────────────────────────────────────────────────┤
│ Orchestration       Orchestrator, Router, AgentContext           │
│                     app/orchestration/*                          │
├─────────────────────────────────────────────────────────────────┤
│ Agents              16 specialists + Guardian                    │
│                     app/agents/*                                 │
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
   d. Asks `router.route_for_trigger(context.trigger)` for the ordered
      diagnostic agent sequence relevant to this problem, and runs exactly
      those agents (not every agent — see `docs/AGENTS.md` for the routing
      table).
   e. Conditionally runs `competitor_intelligence` if external research was
      supplied.
   f. Runs `experimentation`, which scans findings tagged as testable
      hypotheses and proposes deduplicated experiments.
   g. Runs `optimization`, which converts every actionable finding across
      all agents into prioritized `Recommendation` objects — preserving
      disagreement between agents rather than silently picking one.
   h. Persists every finding, recommendation, and experiment to
      `MemoryStore`.
   i. Runs `GuardianAgent.review()` over every recommendation, producing a
      `GuardianDecision` (APPROVE / APPROVE_WITH_CAUTION /
      REQUIRE_HUMAN_APPROVAL / REJECT) for each.
   j. Creates `ApprovalRequest` objects for anything Guardian did not
      reject and that itself requires approval.
   k. Records `ANALYSIS_COMPLETED`.
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
