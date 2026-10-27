import time, json, os, asyncio
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
import openai, anthropic
from google import genai
from google.genai import types

COST_PER_1K = {
    # OpenAI
    "gpt-4o-mini": {"in": 0.00015, "out": 0.0006},
    "gpt-4o": {"in": 0.005, "out": 0.015},
    # Anthropic
    "claude-3-5-sonnet-20240620": {"in": 0.003, "out": 0.015},
    "claude-3-5-haiku-20241022": {"in": 0.001, "out": 0.005},
    # Gemini - update with current pricing
    "gemini-2.0-flash": {"in": 0.000075, "out": 0.0003},
    "gemini-1.5-flash": {"in": 0.000075, "out": 0.0003},
    "gemini-1.5-pro": {"in": 0.00125, "out": 0.005},
    "gemini-2.0-flash-lite": {"in": 0.00005, "out": 0.0002},
}

T = TypeVar("T", bound=BaseModel)

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
        
        self.oai = openai.OpenAI() if self.provider == "openai" else None
        self.ant = anthropic.Anthropic() if self.provider == "anthropic" else None
        # Gemini client - reads GEMINI_API_KEY or GOOGLE_API_KEY automatically
        self.gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) if self.provider == "gemini" else None

    def _cost(self, inp, out):
        p = COST_PER_1K.get(self.model, {"in":0, "out":0})
        return (inp/1000 * p["in"]) + (out/1000 * p["out"])

    async def chat(self, system: str, user: str, temperature=0.2) -> LLMResponse:
        start = time.time()
        tin, tout, content = 0, 0, ""

        if self.provider == "openai":
            res = self.oai.chat.completions.create(
                model=self.model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=temperature
            )
            content = res.choices[0].message.content
            tin, tout = res.usage.prompt_tokens, res.usage.completion_tokens

        elif self.provider == "anthropic":
            res = self.ant.messages.create(
                model=self.model, system=system, max_tokens=2000,
                messages=[{"role":"user","content":user}], temperature=temperature
            )
            content = res.content[0].text
            tin, tout = res.usage.input_tokens, res.usage.output_tokens

        elif self.provider == "gemini":
            # Gemini uses system_instruction + contents. Run sync SDK in thread.
            def _call_gemini():
                return self.gemini.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=temperature,
                        max_output_tokens=2000,
                    )
                )
            res = await asyncio.to_thread(_call_gemini)
            content = res.text or ""
            # usage_metadata can be None on errors
            if res.usage_metadata:
                tin = res.usage_metadata.prompt_token_count or 0
                tout = res.usage_metadata.candidates_token_count or 0

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        return LLMResponse(
            content=content, tokens_in=tin, tokens_out=tout,
            cost_usd=self._cost(tin, tout),
            latency_ms=int((time.time()-start)*1000), model=self.model, provider=self.provider
        )

    async def chat_structured(self, system: str, user: str, schema: Type[T], retries=3) -> LLMResponse:
        sys_json = system + f"\nRespond ONLY with valid JSON matching this schema:\n{schema.model_json_schema()}"
        last_err = None
        
        for i in range(retries):
            # Gemini has native JSON mode - use it
            if self.provider == "gemini":
                start = time.time()
                def _call_structured():
                    return self.gemini.models.generate_content(
                        model=self.model,
                        contents=user,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_json,
                            temperature=0.2,
                            response_mime_type="application/json",
                            response_schema=schema, # native Pydantic support
                        )
                    )
                try:
                    res = await asyncio.to_thread(_call_structured)
                    tin = res.usage_metadata.prompt_token_count or 0 if res.usage_metadata else 0
                    tout = res.usage_metadata.candidates_token_count or 0 if res.usage_metadata else 0
                    parsed = schema.model_validate_json(res.text)
                    return LLMResponse(
                        content=res.text, parsed=parsed, tokens_in=tin, tokens_out=tout,
                        cost_usd=self._cost(tin, tout), latency_ms=int((time.time()-start)*1000),
                        model=self.model, provider=self.provider
                    )
                except Exception as e:
                    last_err = e
                    user += f"\n\nPrevious output was invalid: {e}. Fix JSON."
                    continue

            # OpenAI / Anthropic fallback: manual JSON parsing
            resp = await self.chat(sys_json, user, temperature=0.2)
            try:
                txt = resp.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = schema.model_validate_json(txt)
                resp.parsed = parsed
                return resp
            except Exception as e:
                last_err = e
                user += f"\n\nPrevious output was invalid JSON: {e}. Fix it."
        
        raise ValueError(f"Failed structured output after {retries} retries: {last_err}")