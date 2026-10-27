from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from .llm import LLMClient

class SubTask(BaseModel):
    id: str = Field(description="s1, s2...")
    description: str
    tool: Optional[Literal["http_fetch"]] = None # None = pure LLM reasoning
    depends_on: List[str] = Field(default_factory=list)

class Plan(BaseModel):
    reasoning: str
    steps: List[SubTask]

SYSTEM = """You are the PLANNER. Decompose the user's task into 3-5 executable sub-tasks.
Rules:
- Order matters. Use depends_on for DAG.
- Use tool=http_fetch only if you need external URL/data. Otherwise tool=null.
- Keep steps atomic and verifiable."""

async def create_plan(task: str, llm: LLMClient) -> tuple[Plan, dict]:
    resp = await llm.chat_structured(SYSTEM, f"TASK: {task}", Plan)
    # Validate DAG is linear for Phase 1
    if len(resp.parsed.steps) < 2 or len(resp.parsed.steps) > 5:
        raise ValueError("Plan must be 3-5 steps")
    return resp.parsed, resp.model_dump(include={"tokens_in","tokens_out","cost_usd","latency_ms","model"})