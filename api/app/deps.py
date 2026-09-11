"""Dependency injection."""
from app.config import settings
from app.llm import LlmClient, MockLlmClient, RoutingLlmClient


def _build_default() -> LlmClient:
    if settings.llm_provider_mode == "mock":
        return MockLlmClient()
    return RoutingLlmClient(settings)


_llm: LlmClient = _build_default()


def get_llm() -> LlmClient:
    return _llm
