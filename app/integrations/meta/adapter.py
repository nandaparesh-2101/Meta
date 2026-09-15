"""MOCK Meta Ads provider.

Implements `MetaAdsProvider` entirely against the deterministic generator in
`app.integrations.meta.mock_data`. No network call is ever made. Write
methods always return `success=False` with an explanatory message — they
exist to prove out the interface shape, not to pretend a change happened.

A future `LiveMetaAdsProvider` would implement the exact same interface
against the real Meta Marketing API and could be swapped in via
`get_meta_provider()` without touching any agent.
"""

from __future__ import annotations

from datetime import date

from app.config import DataMode, settings
from app.integrations.base import MetaAdsProvider, ProviderActionResult
from app.integrations.meta.mock_data import MockAccountData, generate_full_mock_account
from app.models.ads import Ad, AdSet, Campaign, Creative
from app.models.metrics import DailyInsight


class MockMetaAdsProvider(MetaAdsProvider):
    """MOCK implementation — safe for any environment, no credentials needed."""

    def __init__(self, account_data: MockAccountData | None = None) -> None:
        self._data = account_data or generate_full_mock_account()

    @property
    def is_mock(self) -> bool:
        return True

    def get_campaigns(self) -> list[Campaign]:
        return list(self._data.campaigns)

    def get_adsets(self, campaign_id: str | None = None) -> list[AdSet]:
        ad_sets = self._data.ad_sets
        if campaign_id:
            ad_sets = [a for a in ad_sets if a.campaign_id == campaign_id]
        return list(ad_sets)

    def get_ads(self, ad_set_id: str | None = None) -> list[Ad]:
        ads = self._data.ads
        if ad_set_id:
            ads = [a for a in ads if a.ad_set_id == ad_set_id]
        return list(ads)

    def get_creatives(self, ad_id: str | None = None) -> list[Creative]:
        creatives = self._data.creatives
        if ad_id:
            creatives = [c for c in creatives if c.ad_id == ad_id]
        return list(creatives)

    def get_insights(self, start_date: date, end_date: date, entity_id: str | None = None) -> list[DailyInsight]:
        insights = [i for i in self._data.insights if start_date <= i.date <= end_date]
        if entity_id:
            insights = [
                i for i in insights
                if entity_id in (i.campaign_id, i.ad_set_id, i.ad_id, i.entity_id)
            ]
        return insights

    def update_budget(self, ad_set_id: str, new_daily_budget: float) -> ProviderActionResult:
        return ProviderActionResult(
            success=False,
            message="MockMetaAdsProvider does not perform writes. Execution is disabled in this build.",
        )

    def pause_ad(self, ad_id: str) -> ProviderActionResult:
        return ProviderActionResult(
            success=False,
            message="MockMetaAdsProvider does not perform writes. Execution is disabled in this build.",
        )

    def enable_ad(self, ad_id: str) -> ProviderActionResult:
        return ProviderActionResult(
            success=False,
            message="MockMetaAdsProvider does not perform writes. Execution is disabled in this build.",
        )

    def update_ad(self, ad_id: str, changes: dict) -> ProviderActionResult:
        return ProviderActionResult(
            success=False,
            message="MockMetaAdsProvider does not perform writes. Execution is disabled in this build.",
        )

    def create_ad(self, ad_set_id: str, creative: Creative) -> ProviderActionResult:
        return ProviderActionResult(
            success=False,
            message="MockMetaAdsProvider does not perform writes. Execution is disabled in this build.",
        )


def get_meta_provider() -> MetaAdsProvider:
    """Factory the rest of the app should use instead of instantiating a
    provider directly. Always returns the mock provider in this build,
    regardless of `DATA_MODE`, since no live implementation exists yet —
    but the branch is here so wiring in a real provider later is a one-line
    change, not an architectural change."""
    if settings.data_mode == DataMode.LIVE:
        raise NotImplementedError(
            "DATA_MODE=live is not implemented in this build. Meta API integration is "
            "intentionally not connected. Use DATA_MODE=mock (default)."
        )
    return MockMetaAdsProvider()
