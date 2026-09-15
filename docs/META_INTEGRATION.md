# Meta Integration

## Current state: NOT CONNECTED

This build does not call the Meta Marketing API in any way. `DATA_MODE`
defaults to `mock` and the only code path available is
`MockMetaAdsProvider`. Setting `DATA_MODE=live` raises
`NotImplementedError` explicitly rather than silently falling back to mock
data — the system never pretends to be connected when it isn't.

## The interface (`app/integrations/base.py`)

```python
class MetaAdsProvider(ABC):
    def get_campaigns(self) -> list[Campaign]: ...
    def get_adsets(self, campaign_id: str | None = None) -> list[AdSet]: ...
    def get_ads(self, ad_set_id: str | None = None) -> list[Ad]: ...
    def get_creatives(self, ad_id: str | None = None) -> list[Creative]: ...
    def get_insights(self, start_date, end_date, entity_id=None) -> list[DailyInsight]: ...

    def update_budget(self, ad_set_id: str, new_daily_budget: float) -> ProviderActionResult: ...
    def pause_ad(self, ad_id: str) -> ProviderActionResult: ...
    def enable_ad(self, ad_id: str) -> ProviderActionResult: ...
    def update_ad(self, ad_id: str, changes: dict) -> ProviderActionResult: ...
    def create_ad(self, ad_set_id: str, creative: Creative) -> ProviderActionResult: ...
```

Every agent, the orchestrator, and the execution layer depend on this
interface — never on `MockMetaAdsProvider` or a future
`LiveMetaAdsProvider` directly. `app/integrations/meta/adapter.py`'s
`get_meta_provider()` factory is the only place that decides which
implementation to hand back.

## Adding a real implementation later

1. Create `app/integrations/meta/live_adapter.py` with a
   `LiveMetaAdsProvider(MetaAdsProvider)` class using the official Meta
   Business SDK or direct Graph API calls, translating Meta's JSON
   responses into the exact same typed models (`Campaign`, `AdSet`, `Ad`,
   `Creative`, `DailyInsight`) that `MockMetaAdsProvider` already returns.
2. Read `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` from `app.config.settings`
   (already present in `.env.example`, unused today).
3. Update `get_meta_provider()` in `adapter.py` to return
   `LiveMetaAdsProvider(...)` when `settings.data_mode == DataMode.LIVE`
   and credentials are present.
4. No agent, rule, or orchestrator code changes — they only ever call the
   `MetaAdsProvider` interface methods.
5. Implement the write methods (`update_budget`, `pause_ad`, ...) against
   the real API, but leave `EXECUTION_MODE=disabled` as the default in
   `.env.example` — a live provider existing is not the same as execution
   being authorized. See "Execution safety" below.
6. Add contract tests that run the *same* test suite currently exercised
   against `MockMetaAdsProvider` against `LiveMetaAdsProvider` (behind a
   marker requiring real credentials, skipped by default in CI).

## Execution safety stays independent of the provider

`app/execution/executor.py` checks `settings.execution_mode` before ever
calling a provider write method, and checks the Guardian decision and
approval status before that. Wiring in `LiveMetaAdsProvider` does **not**
by itself enable execution — `EXECUTION_MODE` must also be explicitly
changed away from `disabled`, and even then every write still requires a
non-rejected Guardian decision and (for anything `requires_approval=True`)
an `ApprovalStatus.APPROVED` `ApprovalRequest`.

## What mock mode simulates realistically

`app/integrations/meta/mock_data.py` generates 10 scenarios (strong
campaign, high CPL, cheap-but-low-quality leads, creative fatigue,
audience saturation, high-CTR-poor-conversion, low-CTR-high-quality,
insufficient data, scaling opportunity, tracking anomaly) with internally
consistent funnel data (reach <= impressions, leads derived from actual
landing page views, qualified/sale counts derived from the same lead
records referenced in `Sale.lead_id`) so agents are exercised against
believable, not just plausible-looking, data.
