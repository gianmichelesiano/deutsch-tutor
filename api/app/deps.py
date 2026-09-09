"""Dependency injection."""
from app.llm import LlmClient, MockLlmClient

_llm: LlmClient = MockLlmClient()


def get_llm() -> LlmClient:
    return _llm
