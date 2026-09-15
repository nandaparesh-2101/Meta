#!/usr/bin/env python3
"""Runs the full orchestrator against several mock scenarios and prints the
resulting Command Center report for each — a quick way to see the whole
system work end-to-end without starting the API.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations.meta.mock_data import generate_scenario  # noqa: E402
from app.memory.store import MemoryStore  # noqa: E402
from app.orchestration.context import AgentContext  # noqa: E402
from app.orchestration.workflow import Orchestrator  # noqa: E402
from app.reports.command_center import generate_report  # noqa: E402

REFERENCE_DATE = date(2026, 9, 15)

DEMO_RUNS = [
    ("strong_campaign", "scheduled_review"),
    ("high_cpl_campaign", "cpl_increase"),
    ("cheap_low_quality_leads", "cheap_leads_poor_sales"),
    ("tracking_anomaly", "scheduled_review"),
]


def main() -> None:
    memory = MemoryStore(db_path=Path(__file__).resolve().parent.parent / "data" / "runtime" / "demo.db")

    for scenario_key, trigger in DEMO_RUNS:
        account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
        context = AgentContext(
            business_objective=account.business_objective,
            campaigns=account.campaigns,
            ad_sets=account.ad_sets,
            ads=account.ads,
            creatives=account.creatives,
            insights=account.insights,
            leads=account.leads,
            sales=account.sales,
            trigger=trigger,
        )
        orchestrator = Orchestrator(memory=memory)
        result = orchestrator.run(context)
        report = generate_report(context, result.guardian_decisions)

        print("=" * 100)
        print(f"SCENARIO: {scenario_key}  (trigger={trigger})")
        print("=" * 100)
        print(f"Agents executed: {', '.join(result.executed_agents)}")
        print(f"Findings: {len(context.findings)} | Recommendations: {len(context.recommendations)} | "
              f"Guardian decisions: {len(result.guardian_decisions)} | Approvals requested: {len(result.approval_requests)}")
        print()
        print(report.to_markdown())
        print()


if __name__ == "__main__":
    main()
