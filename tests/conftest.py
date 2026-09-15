from __future__ import annotations

from datetime import date

import pytest

from app.integrations.meta.mock_data import generate_full_mock_account, generate_scenario
from app.memory.store import MemoryStore
from app.orchestration.context import AgentContext

REFERENCE_DATE = date(2026, 9, 15)


@pytest.fixture
def memory_store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test_memory.db")


@pytest.fixture
def full_mock_account():
    return generate_full_mock_account(reference_date=REFERENCE_DATE)


def build_context(account, trigger: str = "scheduled_review", **overrides) -> AgentContext:
    kwargs = dict(
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
    kwargs.update(overrides)
    return AgentContext(**kwargs)


@pytest.fixture
def scenario_context():
    def _make(scenario_key: str, trigger: str = "scheduled_review"):
        account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
        return build_context(account, trigger=trigger)

    return _make
