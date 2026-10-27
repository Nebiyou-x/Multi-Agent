from pydantic import BaseModel, Field
from typing import Optional
from .llm import LLMClient
from packages.tools.registry import tool_registry

SYSTEM_EXEC = """You are the EXECUTOR. You are given a sub-task and a scratchpad (memory of previous steps).
If tool is provided, you will be given tool output. Otherwise reason and produce output.
Be concise and factual. Always cite URLs if used."""

# Tools whose arguments the LLM must extract from the task description
class UrlRequest(BaseModel):
    url: str = Field(description="The single URL to fetch")

SYSTEM_URL = "Extract the single URL the sub-task needs. Respond with JSON only: {\"url\": \"...\"}."

async def execute_step(task: str, subtask, scratchpad: dict, llm: LLMClient):
    """Execute one sub-task. Never raises for tool failures - they are returned
    so the orchestrator can trace them and let the critic act on them."""
    tool_output: Optional[dict] = None
    tool_error: Optional[str] = None

    if subtask.tool:
        tool = tool_registry.get(subtask.tool)
        if tool is None:
            # Planner emitted a tool we don't have (e.g. a future sandbox tool)
            tool_error = f"Tool '{subtask.tool}' is not registered; available: {sorted(tool_registry)}"
            tool_output = {"error": tool_error}
        else:
            if subtask.tool == "http_fetch":
                # Structured extraction - tolerant of prose around the URL
                resp = await llm.chat_structured(
                    SYSTEM_URL,
                    f"TASK: {task}\nSUBTASK: {subtask.description}",
                    UrlRequest,
                )
                url = resp.parsed.url.strip()
            else:
                url = subtask.description  # other tools take the description as input
            try:
                tool_output = await tool(url)
            except Exception as e:
                tool_error = f"{type(e).__name__}: {e}"
                tool_output = {"error": tool_error}
                # Remember the bad input so the critic can direct a re-fetch
                if tool_error:
                    scratchpad.setdefault("_tool_failures", {})[subtask.id] = {"url": url, "error": tool_error}

    context = (
        f"TASK: {task}\nSUBTASK: {subtask.description}\n"
        f"SCRATCHPAD: {scratchpad}\nTOOL_OUTPUT: {tool_output}"
    )
    resp = await llm.chat(SYSTEM_EXEC, context)
    return resp.content, tool_output, tool_error, resp.model_dump(include={"tokens_in", "tokens_out", "cost_usd", "latency_ms"})
