"""Meta integration abstraction.

The application depends on this interface, never on a concrete Meta SDK
call. This lets a real `LiveMetaAdsProvider` be added later purely as a new
implementation of `MetaAdsProvider` — no agent, orchestrator, or rule needs
to change.

Every method here maps conceptually to a real Meta Marketing API
capability. Write methods intentionally return a `ProviderActionResult`
rather than performing anything in this build.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from app.models.ads import Ad, AdSet, Campaign, Creative
from app.models.metrics import DailyInsight


@dataclass
class ProviderActionResult:
    success: bool
    message: str
    is_mock: bool = True


class MetaAdsProvider(ABC):
    """Read + write surface every provider implementation must offer.

    Write methods (`update_budget`, `pause_ad`, ...) exist on the interface
    now so agents and the execution layer can be written against a stable
    contract, even though the only implementation available in this build
    (`MockMetaAdsProvider`) never touches a real ad account and the
    execution layer that would call these is disabled by default.
    """

    # -- Read --------------------------------------------------------------

    @abstractmethod
    def get_campaigns(self) -> list[Campaign]: ...

    @abstractmethod
    def get_adsets(self, campaign_id: str | None = None) -> list[AdSet]: ...

    @abstractmethod
    def get_ads(self, ad_set_id: str | None = None) -> list[Ad]: ...

    @abstractmethod
    def get_creatives(self, ad_id: str | None = None) -> list[Creative]: ...

    @abstractmethod
    def get_insights(
        self, start_date: date, end_date: date, entity_id: str | None = None
    ) -> list[DailyInsight]: ...

    # -- Write (disabled/no-op unless a real provider is implemented) ------

    @abstractmethod
    def update_budget(self, ad_set_id: str, new_daily_budget: float) -> ProviderActionResult: ...

    @abstractmethod
    def pause_ad(self, ad_id: str) -> ProviderActionResult: ...

    @abstractmethod
    def enable_ad(self, ad_id: str) -> ProviderActionResult: ...

    @abstractmethod
    def update_ad(self, ad_id: str, changes: dict) -> ProviderActionResult: ...

    @abstractmethod
    def create_ad(self, ad_set_id: str, creative: Creative) -> ProviderActionResult: ...

    @property
    @abstractmethod
    def is_mock(self) -> bool: ...
