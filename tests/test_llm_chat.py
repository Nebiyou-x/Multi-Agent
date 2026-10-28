"""chat() tests for every provider, with the SDK clients mocked out.

No network, no real API keys needed: only response shapes are faked.
"""

import types

import pytest
from packages.agent_core.llm import LLMClient, LLMResponse


@pytest.fixture
def client_factory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    for var in ("LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)

    def make(provider: str, model: str) -> LLMClient:
        return LLMClient(provider=provider, model=model)

    return make


@pytest.fixture
def openai_client(client_factory) -> LLMClient:
    return client_factory("openai", "gpt-4o-mini")


@pytest.fixture
def anthropic_client(client_factory) -> LLMClient:
    return client_factory("anthropic", "claude-haiku-4")


@pytest.fixture
def gemini_client(client_factory) -> LLMClient:
    return client_factory("gemini", "gemini-2.5-flash")


def _oai(response):
    """Wrap a fake response object into the openai client shape."""
    async def create(**kwargs):
        return response

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )


def _anthropic(response):
    async def create(**kwargs):
        return response

    return types.SimpleNamespace(messages=types.SimpleNamespace(create=create))


def _gemini(response):
    class _Models:
        @staticmethod
        def generate_content(**kwargs):
            return response

    return types.SimpleNamespace(models=_Models())


def _openai_response(content="hello world", tin=10, tout=5):
    usage = types.SimpleNamespace(prompt_tokens=tin, completion_tokens=tout)
    choice = types.SimpleNamespace(message=types.SimpleNamespace(content=content))
    return types.SimpleNamespace(choices=[choice], usage=usage)


def _anthropic_response(text="claude says hi", tin=8, tout=4):
    block = types.SimpleNamespace(type="text", text=text)
    usage = types.SimpleNamespace(input_tokens=tin, output_tokens=tout)
    return types.SimpleNamespace(content=[block], usage=usage)


def _gemini_response(text="gemini text", tin=12, tout=6):
    usage = types.SimpleNamespace(prompt_token_count=tin, candidates_token_count=tout)
    return types.SimpleNamespace(text=text, usage_metadata=usage)


class TestOpenAIChat:
    async def test_returns_full_response(self, openai_client, client_factory):
        client = openai_client
        client.oai = _oai(_openai_response())

        res = await client.chat("sys", "user")

        assert isinstance(res, LLMResponse)
        assert res.content == "hello world"
        assert res.tokens_in == 10
        assert res.tokens_out == 5
        assert res.provider == "openai"
        assert res.model == "gpt-4o-mini"
        # gpt-4o-mini: 10 in -> 0.0015, 5 out -> 0.003
        assert res.cost_usd == pytest.approx(0.0045)

    async def test_sends_correct_messages(self, openai_client):
        client = openai_client
        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return _openai_response()

        client.oai = _oai(_openai_response())
        client.oai.chat.completions.create = create

        await client.chat("sys", "user")
        assert captured["model"] == "gpt-4o-mini"
        assert captured["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "user"},
        ]
        assert captured["temperature"] == 0.2

    async def test_none_content_defaults_to_empty_string(self, openai_client):
        client = openai_client
        client.oai = _oai(_openai_response(content=None, tin=0, tout=0))
        res = await client.chat("s", "u")
        assert res.content == ""


class TestAnthropicChat:
    async def test_returns_full_response(self, anthropic_client):
        client = anthropic_client
        client.ant = _anthropic(_anthropic_response())

        res = await client.chat("sys", "user")
        assert res.content == "claude says hi"
        assert res.tokens_in == 8
        assert res.tokens_out == 4
        assert res.provider == "anthropic"
        # claude-haiku-4: 8 in -> 0.008, 4 out -> 0.02
        assert res.cost_usd == pytest.approx(0.028)

    async def test_sends_correct_args(self, anthropic_client):
        client = anthropic_client
        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return _anthropic_response()

        client.ant = _anthropic(_anthropic_response())
        client.ant.messages.create = create

        await client.chat("sys", "user")
        assert captured["max_tokens"] == 4000
        assert captured["system"] == "sys"
        assert captured["messages"] == [{"role": "user", "content": "user"}]


class TestGeminiChat:
    async def test_returns_full_response(self, gemini_client):
        client = gemini_client
        client.gemini = _gemini(_gemini_response())

        res = await client.chat("sys", "user")
        assert res.content == "gemini text"
        assert res.tokens_in == 12
        assert res.tokens_out == 6
        assert res.provider == "gemini"
        # gemini-2.5-flash: 12 in -> 0.0018, 6 out -> 0.0036
        assert res.cost_usd == pytest.approx(0.0054)

    async def test_missing_usage_metadata_defaults_to_zero(self, gemini_client, client_factory):
        client = client_factory("gemini", "gemini-2.0-flash")
        fake = types.SimpleNamespace(text="ok", usage_metadata=None)
        client.gemini = _gemini(fake)

        res = await client.chat("s", "u")
        assert res.tokens_in == 0
        assert res.tokens_out == 0

    async def test_sends_system_instruction(self, gemini_client):
        client = gemini_client
        captured = {}

        class _Models:
            @staticmethod
            def generate_content(**kwargs):
                captured.update(kwargs)
                return _gemini_response()

        client.gemini = types.SimpleNamespace(models=_Models())
        await client.chat("sys", "user")
        assert captured["contents"] == "user"
        assert captured["config"].system_instruction == "sys"


class TestLatency:
    async def test_latency_ms_is_int(self, openai_client):
        client = openai_client
        client.oai = _oai(_openai_response(content="x", tin=1, tout=1))
        res = await client.chat("s", "u")
        assert isinstance(res.latency_ms, int)
        assert res.latency_ms >= 0
