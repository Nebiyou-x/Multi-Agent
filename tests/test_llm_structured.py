"""chat_structured() tests per provider, with SDK clients mocked.

Covers: successful parse, provider-specific mechanics (OpenAI json_schema,
Anthropic tool_use, Gemini response_schema), and the retry -> ValueError path.
"""

import json
import types

import pytest
from pydantic import BaseModel
from packages.agent_core.llm import LLMClient, LLMResponse


class Plan(BaseModel):
    step: str
    confidence: float


@pytest.fixture
def clients(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    for var in ("LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)

    return {
        "openai": LLMClient(provider="openai", model="gpt-4o-mini"),
        "anthropic": LLMClient(provider="anthropic", model="claude-haiku-4"),
        "gemini": LLMClient(provider="gemini", model="gemini-2.5-flash"),
    }


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
class TestStructuredOpenAI:
    async def test_success_parses_model(self, clients):
        client = clients["openai"]
        payload = json.dumps({"step": "run tests", "confidence": 0.9})

        fake_res = types.SimpleNamespace(
            usage=types.SimpleNamespace(prompt_tokens=20, completion_tokens=10),
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=payload))],
        )

        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return fake_res

        client.oai = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        )

        res = await client.chat_structured("sys", "user", Plan)
        assert isinstance(res, LLMResponse)
        assert isinstance(res.parsed, Plan)
        assert res.parsed.step == "run tests"
        assert res.parsed.confidence == 0.9
        # Must ask OpenAI for strict json_schema.
        rf = captured["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["name"] == "structured_output"
        assert "step" in rf["json_schema"]["schema"]["properties"]

    async def test_retries_then_raises_on_failure(self, clients):
        client = clients["openai"]
        attempts = {"n": 0}

        async def create(**kwargs):
            attempts["n"] += 1
            raise ValueError("bad json")

        client.oai = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        )

        with pytest.raises(ValueError, match="Failed structured output after 2 retries"):
            await client.chat_structured("sys", "user", Plan, retries=2)
        assert attempts["n"] == 2

    def test_schema_strips_optional_keys(self):
        js = LLMClient._schema_to_dict(Plan)
        assert "$schema" not in js
        assert "title" not in js
        assert "properties" in js
        assert "step" in js["properties"]


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class TestStructuredAnthropic:
    async def test_success_via_tool_use(self, clients):
        client = clients["anthropic"]

        tool_block = types.SimpleNamespace(type="tool_use", input={"step": "x", "confidence": 0.5})
        fake_res = types.SimpleNamespace(
            usage=types.SimpleNamespace(input_tokens=3, output_tokens=7),
            content=[tool_block],
        )

        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return fake_res

        client.ant = types.SimpleNamespace(
            messages=types.SimpleNamespace(create=create)
        )

        res = await client.chat_structured("sys", "user", Plan)
        assert isinstance(res.parsed, Plan)
        assert json.loads(res.content) == {"step": "x", "confidence": 0.5}
        # Tool choice must force the (dynamic) tool name derived from the schema.
        assert captured["tool_choice"] == {"type": "tool", "name": "submit_plan"}
        assert captured["tools"][0]["name"] == "submit_plan"

    async def test_missing_tool_block_retries_then_raises(self, clients):
        client = clients["anthropic"]
        attempts = {"n": 0}
        # No tool_use block -> code raises -> retry loop runs to exhaustion.
        fake_res = types.SimpleNamespace(
            usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
            content=[],
        )

        async def create(**kwargs):
            attempts["n"] += 1
            return fake_res

        client.ant = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))

        with pytest.raises(ValueError, match="after 2 retries"):
            await client.chat_structured("sys", "user", Plan, retries=2)
        assert attempts["n"] == 2

    async def test_invalid_tool_input_retries(self, clients):
        client = clients["anthropic"]
        # `step` must be a str; 123 fails validation and should trigger a retry.
        bad_block = types.SimpleNamespace(type="tool_use", input={"step": 123})
        fake_res = types.SimpleNamespace(
            usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
            content=[bad_block],
        )

        async def create(**kwargs):
            return fake_res

        client.ant = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))

        with pytest.raises(ValueError):
            await client.chat_structured("sys", "user", Plan, retries=1)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
class TestStructuredGemini:
    async def test_success_parses_model(self, clients):
        client = clients["gemini"]
        payload = json.dumps({"step": "g", "confidence": 0.7})
        fake_res = types.SimpleNamespace(
            text=payload,
            usage_metadata=types.SimpleNamespace(prompt_token_count=4, candidates_token_count=2),
        )

        captured = {}

        class _Models:
            @staticmethod
            def generate_content(**kwargs):
                captured.update(kwargs)
                return fake_res

        client.gemini = types.SimpleNamespace(models=_Models())

        res = await client.chat_structured("sys", "user", Plan)
        assert isinstance(res.parsed, Plan)
        assert res.parsed.step == "g"
        # Must pass the Pydantic model straight through as response_schema.
        assert captured["config"].response_schema is Plan
        assert captured["config"].response_mime_type == "application/json"

    async def test_retry_then_raises(self, clients):
        client = clients["gemini"]
        attempts = {"n": 0}

        class _Models:
            @staticmethod
            def generate_content(**kwargs):
                attempts["n"] += 1
                raise RuntimeError("boom")

        client.gemini = types.SimpleNamespace(models=_Models())

        with pytest.raises(ValueError, match="after 3 retries"):
            await client.chat_structured("sys", "user", Plan, retries=3)
        assert attempts["n"] == 3
