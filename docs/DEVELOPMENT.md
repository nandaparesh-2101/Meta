# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No `.env` file is required. Copy `.env.example` to `.env` only to override
a default (data mode, execution mode, database path).

## Running things

```bash
python scripts/generate_mock_data.py   # regenerate data/mock/*.json
python scripts/run_demo.py             # run 4 scenarios end-to-end, print reports
pytest -q                              # full test suite
pytest -q -k scenarios                 # just the 10 mock-scenario tests
uvicorn app.main:app --reload          # API on http://localhost:8000 (docs at /docs)
```

## Conventions

- **Typed everywhere.** Pass Pydantic models between layers, never raw
  dicts, when a model exists for the data. `AgentContext` (a dataclass, not
  a Pydantic model, since it's mutable working state rather than a
  validated payload) is the one exception.
- **Agents never touch storage directly.** They read from `AgentContext`
  and return `list[AgentFinding]`. Only `Orchestrator` persists to
  `MemoryStore`.
- **Never fabricate a metric.** `app/metrics/engine.py` returns `None` on
  any zero-denominator or missing-input case — never `0.0`, which would
  read as "perfect" or "free." Every agent must handle `None` explicitly
  when formatting output.
- **Never claim more confidence than the evidence supports.**
  `BaseAgent.run()` caps `confidence` against
  `rules.data_sufficiency.confidence_ceiling()` automatically; don't try
  to work around this in a new agent.
- **Guardian is the last line, not a rubber stamp.** Any new recommendation
  type should be exercised against `app/rules/safety_rules.py`'s checks in
  a test before being considered done.
- **No fake LLM calls.** If you add real LLM reasoning, implement it as a
  new `LLMProvider` (see `app/llm/provider.py`) and make sure the mock
  path continues to work with zero API keys. Never have an agent format a
  string and call it "the model's reasoning" without an actual
  `LLMProvider.complete()` call.

## Testing requirements for new work

- Unit test any new pure function (metrics, rules).
- If you add or change an agent, add or update a scenario assertion in
  `tests/test_orchestrator_scenarios.py`.
- If you add a new recommendation `ActionType`, add a Guardian test
  confirming it gets a sensible risk/verdict.
- Run `pytest -q` before considering a change complete — CI-equivalent
  local check.

## Database

SQLite, path from `settings.sqlite_path` (default
`data/runtime/meta_ads_ai.db`, gitignored). Schema is created
automatically by `MemoryStore.__init__` (`app/memory/store.py`) — there is
no separate migration step in this build; if you add a table, add it to
`SCHEMA` in that file (idempotent `CREATE TABLE IF NOT EXISTS`).

## Adding a specialist agent

See "Adding a new agent" in `docs/AGENTS.md`.
