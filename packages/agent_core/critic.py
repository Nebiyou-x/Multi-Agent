from pydantic import BaseModel
from typing import Literal
from .llm import LLMClient

class CriticVerdict(BaseModel):
    verdict: Literal["PASS", "REVISE"]
    feedback: str
    score: float = Field(ge=0, le=1)

SYSTEM_CRITIC = """You are the CRITIC. Given TASK, SCRATCHPAD, and FINAL OUTPUT, decide PASS or REVISE.
PASS if output fully answers task with evidence.
REVISE if missing data, hallucination, no citations, or wrong format. Be strict. Max 3 sentences feedback."""

async def critique(task: str, scratchpad: dict, final_output: str, llm: LLMClient):
    resp = await llm.chat_structured(
        SYSTEM_CRITIC,
        f"TASK: {task}\nSCRATCHPAD: {scratchpad}\nOUTPUT: {final_output}",
        CriticVerdict
    )
    return resp.parsed, resp.model_dump(include={"tokens_in","tokens_out","cost_usd","latency_ms"})