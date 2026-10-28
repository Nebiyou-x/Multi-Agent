"""Constructor/provider-selection tests for LLMClient. No network calls."""

import pytest
from pydantic import BaseModel

from packages.agent_core.llm import LLMClient


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    for var in ("LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_explicit_provider_and_model(keys):
    c = LLMClient(provider="anthropic", model="claude-haiku-4")
    assert c.provider == "anthropic"
    assert c.model == "claude-haiku-4"
    assert c.oai is None
    assert c.ant is not None
    assert c.gemini is None


def test_openai_provider_builds_only_openai_client(keys):
    c = LLMClient(provider="openai", model="gpt-4o")
    assert c.oai is not None
    assert c.ant is None
    assert c.gemini is None


def test_gemini_provider_builds_only_gemini_client(keys):
    c = LLMClient(provider="gemini", model="gemini-2.5-flash")
    assert c.oai is None
    assert c.ant is None
    assert c.gemini is not None


def test_provider_is_case_insensitive(keys):
    c = LLMClient(provider="OpenAI", model="gpt-4o-mini")
    assert c.provider == "openai"


def test_env_var_defaults(keys):
    keys.setenv("LLM_PROVIDER", "anthropic")
    keys.setenv("LLM_MODEL", "claude-opus-4")
    c = LLMClient()
    assert c.provider == "anthropic"
    assert c.model == "claude-opus-4"


def test_built_in_defaults_without_env(keys):
    c = LLMClient()
    assert c.provider == "openai"
    assert c.model == "gpt-4o-mini"


def test_gemini_key_falls_back_to_google_api_key(monkeypatch):
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-fallback-key")
    c = LLMClient(provider="gemini", model="gemini-2.0-flash")
    assert c.gemini is not None


@pytest.mark.asyncio
async def test_unknown_provider_rejected_in_chat(keys):
    c = LLMClient(provider="mistral", model="mistral-small")
    with pytest.raises(ValueError, match="Unknown provider: mistral"):
        await c.chat("sys", "user")


@pytest.mark.asyncio
async def test_unknown_provider_rejected_in_structured_chat(keys):
    c = LLMClient(provider="mistral", model="mistral-small")

    class Out(BaseModel):
        x: int

    with pytest.raises(ValueError, match="Unknown provider: mistral"):
        await c.chat_structured("sys", "user", Out)
