"""Unit tests for the cost table, _cost helper, and LLMResponse defaults.

No network, no API keys required.
"""

import pytest
from pydantic import BaseModel
from packages.agent_core.llm import LLMClient, LLMResponse, COST_PER_1K


@pytest.fixture
def client(monkeypatch):
    # Keys so the constructor's SDK clients can be built; calls are mocked anyway.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    for var in ("LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return LLMClient(provider="openai", model="gpt-4o-mini")


class TestCostPer1K:
    def test_known_model_prices(self):
        assert COST_PER_1K["gpt-4o-mini"] == {"in": 0.15, "out": 0.60}
        assert COST_PER_1K["claude-opus-4"] == {"in": 5.0, "out": 25.0}

    def test_unknown_model_costs_zero(self, client):
        client.model = "some-unknown-model"
        assert client._cost(1000, 1000) == 0.0

    def test_zero_tokens_cost_zero(self, client):
        assert client._cost(0, 0) == 0.0

    def test_cost_is_linear_in_tokens(self, client):
        # gpt-4o-mini: 1000 in -> $0.15, 1000 out -> $0.60
        assert client._cost(1000, 1000) == pytest.approx(0.75)
        assert client._cost(500, 200) == pytest.approx(0.075 + 0.12)

    def test_fractional_tokens(self, client):
        # 10 in -> $0.0015, 5 out -> $0.003
        assert client._cost(10, 5) == pytest.approx(0.0045)


class TestLLMResponse:
    def test_defaults(self):
        r = LLMResponse(content="hi", model="gpt-4o-mini", provider="openai")
        assert r.parsed is None
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.cost_usd == 0.0
        assert r.latency_ms == 0

    def test_parsed_accepts_a_base_model(self):
        class Thing(BaseModel):
            x: int = 1

        r = LLMResponse(content="{}", model="m", provider="p", parsed=Thing(x=2))
        assert isinstance(r.parsed, Thing)
        assert r.parsed.x == 2
