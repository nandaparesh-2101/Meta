# Meta Ads AI Growth & Optimization OS

A multi-agent system that analyzes Meta Ads performance, diagnoses root
causes, and produces evidence-backed, safety-reviewed optimization
recommendations.

**Current status: MOCK DATA MODE.** No Meta Marketing API account is
connected. No real advertising change can be executed by this codebase.
Everything described below runs against a deterministic, clearly-labeled
mock dataset.

## What this is

70 agents total — the original 16 core specialists (business economics,
data analysis, campaign structure, audience, creative, copy,
offer/psychology, lead quality, funnel diagnostics, experimentation,
budget/scaling, forecasting, attribution, competitor intelligence, and
optimization decision-making) plus a V2 expansion of 54 advanced
specialists (customer avatar & language mining, buyer awareness, hook/UGC/
video/static creative generation, creative fatigue prediction & refresh &
scoring & diversity, landing page/CRO/form/lead-response/CRM/sales
intelligence, tracking data quality/statistics/anomaly detection, offer
testing & objection mining & social proof, funnel economics & marginal
performance & scaling risk & budget simulation, post-change verification &
rollback decisions, learning synthesis & knowledge graph, ad policy & brand
safety/voice/content-quality governance, and portfolio/prioritization/
executive-strategy synthesis) — plus a Guardian agent with veto power,
coordinated by a Master Orchestrator that routes only the agents relevant
to a given problem — never every agent for every request. See
`docs/AGENTS.md` for the full 70-agent catalog and routing table.

The pipeline is: **DATA -> INTELLIGENCE -> ROOT CAUSE -> STRATEGY ->
EXPERIMENT -> VALIDATION -> SAFE OPTIMIZATION -> MEASUREMENT -> LEARNING**.

See `docs/ARCHITECTURE.md` for the full system design, `docs/AGENTS.md` for
what each agent does, and `docs/META_INTEGRATION.md` for how a real Meta
API connection would be added later without rewriting any agent.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate the mock dataset (also writes it to data/mock/*.json for inspection)
python scripts/generate_mock_data.py

# Run the test suite
pytest -q

# Run a demo analysis end-to-end from the command line
python scripts/run_demo.py

# Run the API
uvicorn app.main:app --reload
# then: curl http://localhost:8000/health
#       curl -X POST http://localhost:8000/analyze -H 'Content-Type: application/json' \
#            -d '{"trigger": "cpl_increase", "scenario": "high_cpl_campaign"}'
```

No `.env` file or API keys are required for any of the above. Copy
`.env.example` to `.env` only if you want to override defaults.

## API surface

| Method | Path          | Purpose                                                   |
|--------|---------------|------------------------------------------------------------|
| GET    | `/health`     | Liveness check                                              |
| GET    | `/status`     | Data mode, execution mode, available triggers/scenarios     |
| POST   | `/analyze`    | Run the full orchestrator against mock data, get a report   |
| POST   | `/recommend`  | Fetch persisted recommendations                              |
| GET    | `/experiments`| List all tracked experiments                                 |
| GET    | `/learnings`  | List recorded learnings                                      |
| GET    | `/audit`      | List audit log events                                        |
| POST   | `/execute`    | Always reports execution is disabled (safety gate is visible)|

## Project structure

```
app/
  agents/          70 agents (16 core + 54 V2 specialists) + Guardian + BaseAgent framework + registry.py
  orchestration/    Router (intelligent agent selection), Orchestrator, AgentContext
  models/           Pydantic domain models (ads, leads, metrics, recommendations, ...)
  memory/           SQLite-backed findings/recommendations/experiments/learnings/audit store
  rules/            KPI evaluation, data sufficiency, scaling limits, safety checks
  metrics/          Pure metric calculation engine (CTR, CPL, ROAS, ...)
  integrations/     MetaAdsProvider interface + MockMetaAdsProvider
  execution/        Approval, executor, rollback (safety-gated, disabled by default)
  reports/          Command Center report generator
  api/               FastAPI routes
  llm/               LLMProvider interface + deterministic MockLLMProvider
  config.py          Environment-driven settings (no secrets required)
data/mock/           Generated mock dataset (JSON, for inspection)
data/runtime/        SQLite database lives here (gitignored)
tests/                pytest suite (93+ tests, including 10 mock-scenario tests)
docs/                 Architecture, agents, Meta integration, optimization rules, dev guide
scripts/               generate_mock_data.py, run_demo.py
```

## What is intentionally NOT connected

- **Meta Marketing API** — `MetaAdsProvider` is a real interface;
  `MockMetaAdsProvider` is the only implementation. No network call to
  Meta is ever made.
- **A real LLM** — `LLMProvider` is a real interface; `MockLLMProvider` is
  deterministic and used by default. Setting `LLM_PROVIDER=anthropic`
  without also implementing `AnthropicLLMProvider.complete()` raises
  `NotImplementedError` rather than faking a response.
- **Execution** — `EXECUTION_MODE=disabled` by default. Even in another
  mode, `MockMetaAdsProvider`'s write methods always refuse to act.

## What should be built next

1. A real `LiveMetaAdsProvider` implementing `MetaAdsProvider` against the
   Meta Marketing API (read-only first).
2. A real `AnthropicLLMProvider` for narrative reasoning/summaries layered
   on top of the existing deterministic agent logic (which should remain
   the source of truth for numeric findings).
3. A human approval UI/CLI consuming `GET /audit` and the `approvals` table.
4. Statistical significance testing in `ExperimentResult` generation
   (currently a placeholder decision rule the calling code must satisfy).
5. Multi-account / multi-business support (currently one `BusinessObjective`
   per orchestration run).
