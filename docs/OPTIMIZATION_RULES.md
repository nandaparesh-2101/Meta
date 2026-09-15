# Optimization Rules

These are the hard, testable rules the system enforces — not vibes.

## Data sufficiency (`app/rules/data_sufficiency.py`)

Every finding/recommendation is classified against explicit minimums
(default 7 days / 50 samples, tunable per-agent):

| Level | Meaning | Confidence ceiling |
|-------|---------|---------------------|
| `INSUFFICIENT_DATA` | Below half the minimum on either axis | 0.25 |
| `EARLY_SIGNAL` | Below the minimum, not by much | 0.50 |
| `PROMISING` | Meets both minimums | 0.75 |
| `CONFIDENT` | >=2x both minimums | 0.95 |

`BaseAgent.run()` enforces the confidence ceiling automatically — an
agent's own `confidence` value is silently capped, never trusted blindly.

## KPI evaluation (`app/rules/kpi_rules.py`)

A metric is only ever "good" or "bad" relative to the business's own
`KPIConfiguration` (`target_cpl`, `target_qualified_cpl`, `target_cac`,
`target_roas`) — never a hardcoded industry benchmark. A 15% tolerance band
separates `ON_TARGET` from `OFF_TARGET`, with `BORDERLINE` in between.

## Scaling limits (`app/rules/scaling_rules.py`)

A proposed budget change is safe only if **all** of:

1. `days_running >= constraints.min_data_days_before_scaling` (default 7).
2. The percentage change does not exceed
   `constraints.max_budget_change_pct_per_change`, itself scaled down
   further by data sufficiency (0% allowed at `INSUFFICIENT_DATA`, 25% of
   the ceiling at `EARLY_SIGNAL`, 60% at `PROMISING`, 100% at `CONFIDENT`).
3. The proposed budget does not exceed `constraints.max_daily_budget`.

## Safety checks Guardian runs (`app/rules/safety_rules.py`)

- `check_data_sufficiency` — blocks anything based on `INSUFFICIENT_DATA`.
- `check_budget_risk` — flags missing budget baseline and protected
  campaigns.
- `check_excessive_scaling` — flags a single-step change over 50%.
- `check_confidence_vs_risk` — flags high risk paired with <0.6 confidence.
- `check_duplicate_experiment` — blocks re-testing an identical hypothesis.
- `check_missing_measurement_plan` — every recommendation must state how
  success will be measured.
- `check_tracking_anomaly` — recommendations built on data already flagged
  with a `tracking_anomaly` tag are treated with extra suspicion.

Guardian verdicts:

| Verdict | Meaning |
|---------|---------|
| `APPROVE` | No concerns, low risk. |
| `APPROVE_WITH_CAUTION` | Minor concerns noted but not blocking. |
| `REQUIRE_HUMAN_APPROVAL` | High risk or multiple concerns — a human must review. |
| `REJECT` | A blocking concern (insufficient data, protected campaign, duplicate experiment) — final at this stage. |

## Root cause before recommendation

The orchestrator always runs diagnostic agents (data analyst, creative,
audience, funnel, lead quality, offer, attribution — whichever the router
selects) **before** `optimization` runs. `optimization` only ever converts
findings that already exist; it performs no diagnosis of its own.

## Anti-optimization-noise

`OptimizationAgent` only creates a `Recommendation` from findings that are
`is_actionable()` (has a non-`DO_NOTHING` suggested action). If nothing in
a run clears that bar, the system's own summary finding is literally
`"DO NOTHING YET"` — this is treated as a valid, intentional outcome, not a
failure to find something to say (see
`tests/test_orchestrator_scenarios.py::test_insufficient_data_scenario_never_produces_high_priority_recs`).

## Agent disagreement

When multiple agents suggest different actions for the same entity,
`OptimizationAgent` creates a separate `Recommendation` per distinct
action rather than resolving the conflict silently, and tags the summary
finding `agent_disagreement`. Every one of those recommendations still
goes through Guardian independently.

## Priority levels

| Priority | Assigned when |
|----------|----------------|
| P0 Critical | A `tracking_anomaly` / `offer_risk` tag is present with any non-insufficient data sufficiency. |
| P1 High | High-risk action (budget/pause) with confidence >= 0.6. |
| P2 Medium | `PROMISING`/`CONFIDENT` data sufficiency and confidence >= 0.5. |
| P3 Experimental | Everything else, including all `INSUFFICIENT_DATA`-based findings. |
