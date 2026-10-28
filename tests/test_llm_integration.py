"""Real-network smoke test for LLMClient.

Skipped automatically unless an API key for the configured provider is present.
Run explicitly when you want it:

    pytest tests/test_llm_integration.py -m integration -v
"""

import os

import pytest
from packages.agent_core.llm import LLMClient

pytestmark = pytest.mark.integration

_ENV_KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


@pytest.fixture
def client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "openai")
    key_var = _ENV_KEYS[provider]
    if not os.getenv(key_var):
        pytest.skip(f"No {key_var} set; integration test skipped")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini" if provider == "openai" else "claude-haiku-4")
    return LLMClient(provider=provider, model=model)


@pytest.mark.asyncio
async def test_chat_returns_nonempty_response(client):
    res = await client.chat(
        system="You are a helpful assistant.",
        user="Which number is larger, 9.11 or 9.8? Answer with just the number.",
    )
    assert res.content.strip()
    assert res.model
    assert res.provider in _ENV_KEYS
    assert res.tokens_in >= 0
    assert res.tokens_out >= 0
    assert res.cost_usd >= 0.0
