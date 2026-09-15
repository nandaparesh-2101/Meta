"""LLM provider abstraction.

Agents consume structured context and return structured findings; they must
never be tightly coupled to one model API. This module defines the
interface plus a deterministic `MockLLMProvider` so the whole system is
fully testable and runnable with zero API keys.

IMPORTANT: `AnthropicLLMProvider` below is a NOT-IMPLEMENTED stub. Calling it
raises `NotImplementedError` rather than silently pretending a model call
happened — the system must never fake an LLM response.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import LLMProviderKind, settings


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    context: dict = field(default_factory=dict)
    max_tokens: int = 1024


@dataclass
class LLMResponse:
    text: str
    provider: str
    is_mock: bool
    model: str | None = None


class LLMProvider(ABC):
    """Interface every agent-facing LLM backend must implement."""

    name: str = "base"

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse: ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can actually serve a request right now."""
        ...


class MockLLMProvider(LLMProvider):
    """Deterministic, rule-based stand-in for a real LLM call.

    Agents in this build use their own explicit deterministic logic and only
    fall back to this provider for free-text narrative summaries — it never
    invents numeric findings, it only phrases ones already computed
    elsewhere. This keeps a clear line between "business logic" (real,
    deterministic, testable) and "reasoning narrative" (clearly labeled mock).
    """

    name = "mock"

    def complete(self, request: LLMRequest) -> LLMResponse:
        summary = request.context.get("summary")
        text = (
            summary
            if summary
            else f"[MOCK LLM OUTPUT] {request.user_prompt[:200]}"
        )
        return LLMResponse(text=f"[MOCK] {text}", provider=self.name, is_mock=True, model="mock-deterministic")

    @property
    def is_available(self) -> bool:
        return True


class AnthropicLLMProvider(LLMProvider):
    """NOT IMPLEMENTED in this build.

    Reserved so a future session can add a real Claude-backed reasoning
    layer without touching any agent's call signature.
    """

    name = "anthropic"

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError(
            "AnthropicLLMProvider is not implemented in this build. "
            "Set LLM_PROVIDER=mock (default) to use the deterministic provider."
        )

    @property
    def is_available(self) -> bool:
        return False


def get_llm_provider() -> LLMProvider:
    """Factory honoring `settings.llm_provider`. Falls back to mock whenever
    the configured provider is unavailable — the app must never crash
    because an API key is absent in development mode."""
    if settings.llm_provider == LLMProviderKind.ANTHROPIC and settings.has_llm_credentials:
        provider = AnthropicLLMProvider(settings.anthropic_api_key)
        if provider.is_available:
            return provider
    return MockLLMProvider()
