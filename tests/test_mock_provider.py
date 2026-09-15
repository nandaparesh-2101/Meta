from __future__ import annotations

from datetime import date

from app.config import DataMode
from app.integrations.meta.adapter import MockMetaAdsProvider, get_meta_provider


def test_mock_provider_is_mock():
    provider = MockMetaAdsProvider()
    assert provider.is_mock is True


def test_mock_provider_returns_campaigns_and_related_entities():
    provider = MockMetaAdsProvider()
    campaigns = provider.get_campaigns()
    assert len(campaigns) == 10
    campaign_id = campaigns[0].campaign_id
    ad_sets = provider.get_adsets(campaign_id=campaign_id)
    assert all(a.campaign_id == campaign_id for a in ad_sets)
    ads = provider.get_ads(ad_set_id=ad_sets[0].ad_set_id)
    assert all(a.ad_set_id == ad_sets[0].ad_set_id for a in ads)


def test_mock_provider_insights_filtered_by_date_range():
    provider = MockMetaAdsProvider()
    insights = provider.get_insights(start_date=date(2000, 1, 1), end_date=date(2000, 1, 2))
    assert insights == []


def test_mock_provider_write_methods_never_succeed():
    provider = MockMetaAdsProvider()
    result = provider.pause_ad("ad_123")
    assert result.success is False
    assert result.is_mock is True

    result2 = provider.update_budget("adset_123", 500.0)
    assert result2.success is False


def test_get_meta_provider_factory_returns_mock_by_default():
    provider = get_meta_provider()
    assert provider.is_mock is True


def test_live_data_mode_raises_not_implemented(monkeypatch):
    from app.integrations.meta import adapter

    monkeypatch.setattr(adapter.settings, "data_mode", DataMode.LIVE)
    try:
        raised = False
        try:
            adapter.get_meta_provider()
        except NotImplementedError:
            raised = True
        assert raised
    finally:
        monkeypatch.setattr(adapter.settings, "data_mode", DataMode.MOCK)
