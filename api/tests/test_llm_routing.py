"""Test del layer LLM (task 3.1): routing per task, fallback, retry JSON, validazione."""
from types import SimpleNamespace

import pytest

from app.agents import RoleplayReply
from app.llm import GenerationResult, LlmError, RoutingLlmClient


def _settings(**over) -> SimpleNamespace:
    base = {
        "local_llm_base_url": "http://localhost:8080/v1",
        "local_llm_api_key": "",
        "local_llm_model": "deepseek-v4-flash",
        "anthropic_api_key": "test-key",
        "anthropic_model": "claude-sonnet-4-5",
        "llm_timeout_seconds": 5.0,
        "roleplay_temperature": 0.7,
        "roleplay_max_tokens": 200,
        "cloud_temperature": 0.3,
        "cloud_max_tokens": 1024,
        "llm_provider_mode": "auto",
        "local_llm_thinking_disabled": False,
        "local_llm_repeat_penalty": 0.0,
    }
    base.update(over)
    return SimpleNamespace(**base)


class FakeProvider:
    def __init__(self, name: str, responses: list[str], fail: bool = False):
        self.name = name
        self._responses = list(responses)
        self.calls = 0
        self.fail = fail

    async def generate(self, model, messages, temperature, max_tokens):
        self.calls += 1
        self.last_model = model
        if self.fail:
            raise LlmError("provider down")
        return GenerationResult(text=self._responses.pop(0), provider=self.name, model=model)


def _client(local: FakeProvider, cloud: FakeProvider, mode: str = "auto") -> RoutingLlmClient:
    client = RoutingLlmClient(_settings(llm_provider_mode=mode))
    client.local = local
    client.cloud = cloud
    return client


@pytest.mark.asyncio
async def test_roleplay_routes_to_local():
    local = FakeProvider("local", ['{"text": "Hallo!", "dialogue_closed": false, "translations": []}'])
    cloud = FakeProvider("cloud", [])
    out = await _client(local, cloud).complete("roleplay", [{"role": "user", "content": "hi"}], schema=RoleplayReply)
    assert out["text"] == "Hallo!"
    assert local.calls == 1
    assert cloud.calls == 0


@pytest.mark.asyncio
async def test_corrector_routes_to_cloud():
    local = FakeProvider("local", [])
    cloud = FakeProvider("cloud", ['{"comprehensible": true, "errors": [], "new_words_from_agent": []}'])
    out = await _client(local, cloud).complete("corrector", [{"role": "user", "content": "x"}])
    assert out["comprehensible"] is True
    assert cloud.calls == 1
    assert local.calls == 0


@pytest.mark.asyncio
async def test_roleplay_fallback_local_to_cloud():
    local = FakeProvider("local", [], fail=True)
    cloud = FakeProvider("cloud", ['{"text": "Hi", "dialogue_closed": false, "translations": []}'])
    out = await _client(local, cloud).complete("roleplay", [{"role": "user", "content": "hi"}], schema=RoleplayReply)
    assert out["text"] == "Hi"
    assert cloud.calls == 1


@pytest.mark.asyncio
async def test_retry_on_invalid_json():
    local = FakeProvider(
        "local",
        ["non è JSON", '{"text": "Ok", "dialogue_closed": false, "translations": []}'],
    )
    cloud = FakeProvider("cloud", [])
    out = await _client(local, cloud).complete("roleplay", [{"role": "user", "content": "hi"}], schema=RoleplayReply)
    assert out["text"] == "Ok"
    assert local.calls == 2


@pytest.mark.asyncio
async def test_schema_validation_fails_after_retry():
    local = FakeProvider("local", ['{"wrong": 1}', '{"wrong": 2}'])
    cloud = FakeProvider("cloud", [])
    with pytest.raises(LlmError):
        await _client(local, cloud, mode="local-only").complete(
            "roleplay", [{"role": "user", "content": "hi"}], schema=RoleplayReply
        )
    assert local.calls == 2


@pytest.mark.asyncio
async def test_no_schema_returns_parsed_json():
    local = FakeProvider("local", ['{"a": 1}'])
    cloud = FakeProvider("cloud", [])
    out = await _client(local, cloud).complete("roleplay", [{"role": "user", "content": "hi"}])
    assert out == {"a": 1}


@pytest.mark.asyncio
async def test_local_only_mode_ignores_cloud_routing():
    local = FakeProvider("local", ['{"text": "T", "dialogue_closed": false, "translations": []}'])
    cloud = FakeProvider("cloud", [])
    out = await _client(local, cloud, mode="local-only").complete(
        "corrector", [{"role": "user", "content": "x"}], schema=RoleplayReply
    )
    assert out["text"] == "T"
    assert local.calls == 1
    assert cloud.calls == 0
    # provider forzato a local: il modello deve essere quello locale, non quello cloud
    assert local.last_model == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_cloud_only_mode_uses_cloud_model_for_roleplay():
    local = FakeProvider("local", [])
    cloud = FakeProvider("cloud", ['{"text": "T", "dialogue_closed": false, "translations": []}'])
    await _client(local, cloud, mode="cloud-only").complete(
        "roleplay", [{"role": "user", "content": "x"}], schema=RoleplayReply
    )
    assert local.calls == 0
    assert cloud.last_model == "claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_local_provider_sends_bearer_key(monkeypatch):
    """Il provider OpenAI-compatibile (DeepSeek remoto) deve inviare la chiave API."""
    import httpx

    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = RoutingLlmClient(
        _settings(local_llm_base_url="https://api.deepseek.com", local_llm_api_key="sk-test", local_llm_model="deepseek-flash")
    )
    result = await client.local.generate("deepseek-flash", [{"role": "user", "content": "hi"}], 0.7, 50)
    assert result.text == "ok"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert "repeat_penalty" not in captured["json"]
