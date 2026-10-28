from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from .llm import LLMClient

class SubTask(BaseModel):
    id: str = Field(description="s1, s2...")
    description: str
    tool: Optional[Literal["http_fetch", "code_execution", "sql_query", "web_search"]] = None  # None = pure LLM reasoning
    depends_on: List[str] = Field(default_factory=list)

class Plan(BaseModel):
    reasoning: str
    steps: List[SubTask] = Field(min_length=3, max_length=5)

SYSTEM = """You are the PLANNER. Decompose the user's task into 3-5 executable sub-tasks.
Rules:
- Order matters. Use depends_on for DAG.
- Tool selection:
  - http_fetch: fetch one specific URL/API endpoint.
  - web_search: find sources for a question; no known URL yet.
  - sql_query: read data from the local analytics Postgres (write the SQL in the step description).
  - code_execution: write+run Python (analysis, math, charting) in a sandbox with NO network.
- KEEP NETWORK AND CODE SEPARATED: code_execution can never reach the internet.
  If a step's code needs external data, that data must come from an EARLIER
  http_fetch/web_search step, and this step must declare it in depends_on so its
  output files are mounted read-only into the sandbox.
- For code_execution, the description must state the inputs it needs and what it
  should write to /out (e.g. a PNG chart).
- Keep steps atomic and verifiable."""

def validate_plan(plan: Plan):
    """Strict 3-5 steps, unique IDs, valid depends_on refs, no cycles."""
    ids = [s.id for s in plan.steps]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate subtask ids in plan: {ids}")
    unknown = [d for s in plan.steps for d in s.depends_on if d not in set(ids)]
    if unknown:
        raise ValueError(f"depends_on references unknown step ids: {unknown}")
    # Cycle check (DFS - plan steps are small, O(n^2) is fine)
    state, ids_by_step = {}, {s.id: s for s in plan.steps}
    def visit(nid: str, path: list):
        state[nid] = 1  # visiting
        for dep in ids_by_step[nid].depends_on:
            if state.get(dep) == 1:
                raise ValueError(f"Circular dependency detected: {' -> '.join(path + [dep])}")
            if not state.get(dep):
                visit(dep, path + [dep])
        state[nid] = 2  # done
    for i in ids:
        if not state.get(i):
            visit(i, [i])

async def create_plan(task: str, llm: LLMClient) -> tuple[Plan, dict]:
    resp = await llm.chat_structured(SYSTEM, f"TASK: {task}", Plan)
    plan = resp.parsed
    try:
        validate_plan(plan)
        return plan, resp.model_dump(include={"tokens_in", "tokens_out", "cost_usd", "latency_ms", "model"})
    except ValueError as e:
        # Plan was structurally invalid - try once more, telling the model what broke
        retry = await llm.chat_structured(SYSTEM, f"TASK: {task}\n\nPrevious plan was invalid: {e}. Produce a corrected plan.", Plan)
        plan = retry.parsed
        validate_plan(plan)  # raise if still invalid
        # Account for both LLM calls in the trace metadata
        total = resp.model_dump(include={"tokens_in", "tokens_out", "cost_usd", "latency_ms", "model"})
        extra = retry.model_dump(include={"tokens_in", "tokens_out", "cost_usd", "latency_ms", "model"})
        total["tokens_in"] += extra["tokens_in"]
        total["tokens_out"] += extra["tokens_out"]
        total["cost_usd"] += extra["cost_usd"]
        total["latency_ms"] += extra["latency_ms"]
        return plan, total
