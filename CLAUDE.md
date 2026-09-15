# CLAUDE.md

Source of truth for future Claude Code sessions working in this repository.
This file summarizes; it does not duplicate — for depth see `docs/`.

## What this repository is

A multi-agent Meta Ads AI Growth & Optimization OS, running in **MOCK DATA
MODE**. No Meta Marketing API is connected. No real LLM is called by
default. No advertising change can be executed. See `README.md` for the
full picture, `docs/ARCHITECTURE.md` for system design, `docs/AGENTS.md`
for what each of the 70 agents (16 core + 54 V2 specialists) + Guardian
does, and `app/agents/registry.py` for the machine-readable catalog.

## Hard rules — do not violate these

1. **Never wire up real Meta API execution without explicit user
   instruction.** `EXECUTION_MODE` must stay `disabled` by default.
   `MockMetaAdsProvider`'s write methods must keep returning `success=False`
   unless a real provider is being built on explicit request.
2. **Never fake an LLM response.** If `LLM_PROVIDER=anthropic` and no real
   implementation exists, `AnthropicLLMProvider.complete()` must raise
   `NotImplementedError`, not return a plausible-looking string.
3. **Never have `app/metrics/engine.py` return `0.0` for a missing/zero
   denominator.** Return `None`. Callers must format `None` as "N/A," never
   coerce it.
4. **Never let an agent report confidence above what
   `rules.data_sufficiency.confidence_ceiling()` allows for its data
   sufficiency level.** This is enforced in `BaseAgent.run()` — don't add a
   way around it in a new agent.
5. **Never silently resolve agent disagreement.** If two agents suggest
   different actions for the same entity, both recommendations must be
   created (see `OptimizationAgent`), not just the "winning" one.
6. **Never let `OptimizationAgent` invent a recommendation to avoid an
   empty result.** "DO NOTHING YET" is a valid, intentional, tested
   outcome (`tests/test_orchestrator_scenarios.py`).
7. **Never bypass Guardian.** Every `Recommendation` must go through
   `GuardianAgent.review()` before an `ApprovalRequest` can be created; a
   `REJECT` verdict must block `create_approval_request()` from returning
   anything (see `app/execution/approval.py`).
8. **Never store or pass raw dicts across module boundaries where a typed
   Pydantic model already exists for that data.**
9. **Never fabricate a customer quote, testimonial, statistic, or Meta
   metric.** `CustomerLanguageMiningAgent`, `UGCStrategistAgent`,
   `SocialProofAgent`, etc. must return `"INSUFFICIENT EVIDENCE"` /
   `FindingStatus.INSUFFICIENT_DATA` rather than inventing plausible-sounding
   customer language when no real source text was supplied.
10. **Every registered agent must be reachable by routing.** Adding an
    agent to `AGENT_REGISTRY` without adding it to a route (or the
    always-first/preflight/always-last/conditional lists in
    `workflow.py`/`router.py`) leaves it dead code —
    `tests/test_agent_registry_v2.py::test_every_registered_agent_is_reachable_by_routing`
    enforces this.

## Where things live

- Domain models: `app/models/*` (business, ads, metrics, leads,
  recommendations, experiments, learning, execution, avatar, crm, brand).
- Metric math: `app/metrics/engine.py` — pure functions, `None`-safe.
- Business/safety rules: `app/rules/*`.
- Agents: `app/agents/*` (16 core + 54 V2 specialists across
  customer_intelligence.py, creative_generation.py, creative_ops.py,
  landing_funnel.py, data_quality.py, positioning_offer.py,
  funnel_economics.py, verification.py, learning_intelligence.py,
  governance.py, prioritization.py), registered in
  `app/agents/__init__.py`'s `AGENT_REGISTRY` and cataloged (tier/
  capabilities/dependencies) in `app/agents/registry.py`'s `AGENT_CATALOG`.
- Routing (which agents run for which problem): `app/orchestration/router.py`.
- Master Orchestrator (incl. preflight/capstone agent hooks): `app/orchestration/workflow.py`.
- Persistence (SQLite): `app/memory/store.py` + `app/memory/{experiments,learnings}.py`.
- Meta integration interface + mock: `app/integrations/*`.
- Mock data generator (10 scenarios): `app/integrations/meta/mock_data.py`.
- Execution safety pipeline: `app/execution/{approval,executor,rollback}.py`.
- Reporting: `app/reports/command_center.py`.
- API: `app/api/routes.py`, `app/main.py`.

## Testing requirements

Run `pytest -q` before considering any change complete. If you touch an
agent, update `tests/test_orchestrator_scenarios.py`. If you touch a rule
in `app/rules/`, add/update a direct unit test for it — don't rely only on
the scenario tests to catch a regression. See `docs/DEVELOPMENT.md` for
the full testing workflow.

## Coding conventions

- Type everything; avoid `dict` where a Pydantic model exists.
- Agents are stateless: `analyze(self, context) -> list[AgentFinding]`,
  no side effects on storage. Only `Orchestrator` writes to `MemoryStore`.
- Keep deterministic business logic (metric math, thresholds, routing)
  separate from any future LLM-generated narrative text — the latter must
  never be the source of a numeric finding.
- Comments only where the *why* isn't obvious from the code; no docstring
  bloat, no restating the function name in prose.
