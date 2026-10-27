from .llm import LLMClient
from packages.tools.registry import tool_registry

SYSTEM_EXEC = """You are the EXECUTOR. You are given a sub-task and a scratchpad (memory of previous steps).
If tool is provided, you will be given tool output. Otherwise reason and produce output.
Be concise and factual. Always cite URLs if used."""

async def execute_step(task: str, subtask, scratchpad: dict, llm: LLMClient):
    # 1. If tool needed, call it
    tool_output = None
    if subtask.tool:
        tool = tool_registry.get(subtask.tool)
        # For http_fetch, LLM must first extract URL from description if not given
        # Phase 1 simple: let LLM propose URL
        url_resp = await llm.chat(
            system="Extract the single URL to fetch from the task. Respond with URL only.",
            user=f"TASK: {task}\nSUBTASK: {subtask.description}"
        )
        url = url_resp.content.strip()
        tool_output = await tool(url) # returns dict

    # 2. LLM synthesizes step output using scratchpad + tool_output
    context = f"TASK: {task}\nSUBTASK: {subtask.description}\nSCRATCHPAD: {scratchpad}\nTOOL_OUTPUT: {tool_output}"
    resp = await llm.chat(SYSTEM_EXEC, context)
    return resp.content, tool_output, resp.model_dump(include={"tokens_in","tokens_out","cost_usd","latency_ms"})