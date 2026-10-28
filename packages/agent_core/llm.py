import time, json, os, asyncio
from typing import Optional, Type, TypeVar, Any, Dict
from pydantic import BaseModel, Field
import openai
import anthropic
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from google.genai import types

# Approximate USD per 1K tokens. Unknown models default to 0 - refresh periodically.
COST_PER_1K = {
    # OpenAI
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 2.50, "out": 10.0},
    "gpt-4.1": {"in": 2.0, "out": 8.0},
    # Anthropic
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    "claude-haiku-4": {"in": 1.0, "out": 5.0},
    "claude-opus-4": {"in": 5.0, "out": 25.0},
    "claude-3-5-sonnet-20240620": {"in": 3.0, "out": 15.0},
    "claude-3-5-haiku-20241022": {"in": 0.80, "out": 4.0},
    # Google
    "gemini-2.5-flash": {"in": 0.15, "out": 0.60},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.0},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40},
    "gemini-2.0-flash-lite": {"in": 0.05, "out": 0.15},
}

T = TypeVar("T", bound=BaseModel)

# Transient-transport detection: 5xx / 429 / network-level errors deserve a
# backoff retry; 4xx (auth, invalid model, bad request) must not.
_TRANSIENT_MARKERS = ("429", "500", "502", "503", "504", "rate limit", "ratelimit",
                      "overloaded", "unavailable", "high demand", "connection",
                      "temporarily", "timeout", "timed out")


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if str(code) in {"429", "500", "502", "503", "504"}:
        return True
    return any(m in str(e).lower() for m in _TRANSIENT_MARKERS)


async def _with_retry(fn, attempts: int = 4, base: float = 1.0):
    """Retry a transport call with exponential backoff on transient errors only."""
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            if i == attempts - 1 or not _is_transient(e):
                raise
            await asyncio.sleep(base * (2 ** i))


class LLMResponse(BaseModel):
    content: str
    parsed: Optional[BaseModel] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: str
    provider: str

class LLMClient:
    def __init__(self, provider: str = None, model: str = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        self.oai = AsyncOpenAI() if self.provider == "openai" else None
        self.ant = AsyncAnthropic() if self.provider == "anthropic" else None
        # Gemini client - reads GEMINI_API_KEY or GOOGLE_API_KEY automatically
        self.gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) if self.provider == "gemini" else None

    def _cost(self, inp, out):
        p = COST_PER_1K.get(self.model, {"in": 0, "out": 0})
        return (inp / 1000 * p["in"]) + (out / 1000 * p["out"])

    async def chat(self, system: str, user: str, temperature=0.2) -> LLMResponse:
        start = time.time()
        tin, tout, content = 0, 0, ""

        if self.provider == "openai":
            res = await _with_retry(lambda: self.oai.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature
            ))
            content = res.choices[0].message.content or ""
            tin, tout = res.usage.prompt_tokens, res.usage.completion_tokens

        elif self.provider == "anthropic":
            res = await _with_retry(lambda: self.ant.messages.create(
                model=self.model, system=system, max_tokens=4000,
                messages=[{"role": "user", "content": user}], temperature=temperature
            ))
            content = res.content[0].text
            tin, tout = res.usage.input_tokens, res.usage.output_tokens

        elif self.provider == "gemini":
            # Gemini SDK is sync - run in a thread so the event loop is never blocked
            res = await _with_retry(lambda: asyncio.to_thread(
                self.gemini.models.generate_content,
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    max_output_tokens=4000,
                )
            ))
            content = res.text or ""
            if res.usage_metadata:
                tin = res.usage_metadata.prompt_token_count or 0
                tout = res.usage_metadata.candidates_token_count or 0

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        return LLMResponse(
            content=content, tokens_in=tin, tokens_out=tout,
            cost_usd=self._cost(tin, tout),
            latency_ms=int((time.time() - start) * 1000),
            model=self.model, provider=self.provider
        )

    # ------------------------------------------------------------------
    # Structured output: provider-native JSON mode where available
    # ------------------------------------------------------------------
    async def chat_structured(self, system: str, user: str, schema: Type[T], retries=3) -> LLMResponse:
        if self.provider == "gemini":
            return await self._structured_gemini(system, user, schema, retries)
        if self.provider == "anthropic":
            return await self._structured_anthropic(system, user, schema, retries)
        if self.provider == "openai":
            return await self._structured_openai(system, user, schema, retries)
        raise ValueError(f"Unknown provider: {self.provider}")

    @staticmethod
    def _schema_to_dict(schema: Type[T]) -> Dict[str, Any]:
        """Minimal JSON-Schema (draft-07) for OpenAI's json_schema response_format."""
        js = schema.model_json_schema()
        js.pop("$schema", None)
        js.pop("title", None)
        return js

    async def _structured_openai(self, system: str, user: str, schema: Type[T], retries: int) -> LLMResponse:
        last_err = None
        prompt = user
        for _ in range(retries):
            start = time.time()
            try:
                res = await self.oai.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_schema", "json_schema": {"name": "structured_output", "schema": self._schema_to_dict(schema)}},
                )
                tin, tout = res.usage.prompt_tokens, res.usage.completion_tokens
                content = res.choices[0].message.content or ""
                # Some backends (e.g. NVIDIA NIM) may strip response_format - validate anyway
                parsed = schema.model_validate_json(content.strip())
                return LLMResponse(
                    content=content, parsed=parsed, tokens_in=tin, tokens_out=tout,
                    cost_usd=self._cost(tin, tout), latency_ms=int((time.time() - start) * 1000),
                    model=self.model, provider=self.provider
                )
            except Exception as e:
                last_err = e
                prompt = user + f"\n\nPrevious output was invalid: {e}. Fix the JSON."
        raise ValueError(f"Failed structured output after {retries} retries: {last_err}")

    async def _structured_anthropic(self, system: str, user: str, schema: Type[T], retries: int) -> LLMResponse:
        """Force JSON via a single tool definition - Anthropic's reliable structured-output pattern."""
        tool_name = "submit_" + schema.__name__.lower()
        last_err = None
        prompt = user
        for _ in range(retries):
            start = time.time()
            try:
                res = await self.ant.messages.create(
                    model=self.model, system=system, max_tokens=4000, temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                    tools=[{"name": tool_name, "description": "Submit the structured result", "input_schema": self._schema_to_dict(schema)}],
                    tool_choice={"type": "tool", "name": tool_name},
                )
                tin, tout = res.usage.input_tokens, res.usage.output_tokens
                tool_block = next((b for b in res.content if b.type == "tool_use"), None)
                if tool_block is None:
                    raise ValueError("Model did not call the structured-output tool")
                parsed = schema.model_validate(tool_block.input)
                content = json.dumps(tool_block.input)
                return LLMResponse(
                    content=content, parsed=parsed, tokens_in=tin, tokens_out=tout,
                    cost_usd=self._cost(tin, tout), latency_ms=int((time.time() - start) * 1000),
                    model=self.model, provider=self.provider
                )
            except Exception as e:
                last_err = e
                prompt = user + f"\n\nPrevious output was invalid: {e}. Fix the JSON."
        raise ValueError(f"Failed structured output after {retries} retries: {last_err}")

    async def _structured_gemini(self, system: str, user: str, schema: Type[T], retries: int) -> LLMResponse:
        last_err = None
        prompt = user
        for _ in range(retries):
            start = time.time()
            try:
                res = await _with_retry(lambda: asyncio.to_thread(
                    self.gemini.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=schema,  # native Pydantic support
                    )
                ))
                tin = res.usage_metadata.prompt_token_count or 0 if res.usage_metadata else 0
                tout = res.usage_metadata.candidates_token_count or 0 if res.usage_metadata else 0
                parsed = schema.model_validate_json(res.text)
                return LLMResponse(
                    content=res.text, parsed=parsed, tokens_in=tin, tokens_out=tout,
                    cost_usd=self._cost(tin, tout), latency_ms=int((time.time() - start) * 1000),
                    model=self.model, provider=self.provider
                )
            except Exception as e:
                # Prompt-fix retry only for validation failures; transport
                # failures already got their own backoff inside _with_retry
                # and re-raised, so we surface them immediately.
                last_err = e
                prompt = user + f"\n\nPrevious output was invalid: {e}. Fix the JSON."
        raise ValueError(f"Failed structured output after {retries} retries: {last_err}")
