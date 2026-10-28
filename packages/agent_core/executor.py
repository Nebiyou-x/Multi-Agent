from pydantic import BaseModel, Field
from typing import Optional
from .llm import LLMClient
from packages.tools.registry import tool_registry

SYSTEM_EXEC = """You are the EXECUTOR. You are given a sub-task and a scratchpad (memory of previous steps).
If tool is provided, you will be given tool output. Otherwise reason and produce output.
Be concise and factual. Always cite URLs if used.
When the step produced sandbox artifacts (files in /out), reference them by name in your summary."""

# Structured extraction - LLM pulls clean arguments out of a task description
class UrlRequest(BaseModel):
    url: str = Field(description="The single URL to fetch")

class QueryRequest(BaseModel):
    query: str = Field(description="The query to run")

SYSTEM_URL = "Extract the single URL the sub-task needs. Respond with JSON only: {\"url\": \"...\"}."
SYSTEM_QUERY = "Extract the search query the sub-task needs. Respond with JSON only: {\"query\": \"...\"}."
SYSTEM_SQL = ("Extract the exact single SQL statement the sub-task needs, read-only "
              "Postgres. Respond with JSON only: {\"query\": \"SELECT ...\"}. Do not run DDL or writes.")

SYSTEM_CODE = """You write a single Python script that will run inside a sandbox with:
- NO network access (socket/requests/httpx will fail at runtime - never import or call them)
- read-only input files at /in/<name> (JSON or text, see the listed inputs)
- a writable /out directory for artifacts (e.g. /out/chart.png)
- pandas, numpy, matplotlib (Agg backend, savefig not show)
Write plain script code: read inputs, compute, save artifacts to /out, and print a short summary. No input() calls."""

def _input_files(subtask, scratchpad: dict) -> dict:
    """File I/O protocol: mount dependency outputs into the sandbox read-only.
    - tool outputs (dict)  -> /in/<dep>.json
    - reasoning outputs (text) -> /in/<dep>.txt
    The generated code receives the list of these names in its prompt."""
    files: dict = {}
    for dep in subtask.depends_on:
        tool_out = scratchpad.get(f"_tool_output_{dep}")
        if tool_out is not None:
            files[f"{dep}.json"] = tool_out
        elif dep in scratchpad:
            files[f"{dep}.txt"] = scratchpad[dep]
    return files

async def _generate_code(task: str, subtask, files: dict, llm: LLMClient) -> str:
    """LLM step that writes the sandbox script from the sub-task description."""
    previews = "\n".join(f"- {n}: {str(c)[:400]}" for n, c in files.items()) or "(none)"
    resp = await llm.chat(
        SYSTEM_CODE,
        f"TASK: {task}\nSUBTASK: {subtask.description}\nAVAILABLE INPUT FILES:\n{previews}",
    )
    code = resp.content.strip()
    # tolerate ```python fences
    if code.startswith("```"):
        code = code.strip("`")
        code = code.split("\n", 1)[1] if code.lower().startswith("python") else code
        code = code.rstrip("`").rstrip()
    return code

async def execute_step(task: str, subtask, scratchpad: dict, llm: LLMClient):
    """Execute one sub-task. Never raises for tool failures - they are returned
    so the orchestrator can trace them and let the critic act on them."""
    tool_output: Optional[dict] = None
    tool_error: Optional[str] = None

    if subtask.tool:
        tool = tool_registry.get(subtask.tool)
        if tool is None:
            # Planner emitted a tool we don't have
            tool_error = f"Tool '{subtask.tool}' is not registered; available: {sorted(tool_registry)}"
            tool_output = {"error": tool_error}
        else:
            # --- build the tool arguments ---------------------------------
            if subtask.tool == "http_fetch":
                resp = await llm.chat_structured(SYSTEM_URL, f"TASK: {task}\nSUBTASK: {subtask.description}", UrlRequest)
                args = resp.parsed.url.strip()
            elif subtask.tool == "web_search":
                resp = await llm.chat_structured(SYSTEM_QUERY, f"TASK: {task}\nSUBTASK: {subtask.description}", QueryRequest)
                args = {"query": resp.parsed.query.strip(), "max_results": 5}
            elif subtask.tool == "sql_query":
                resp = await llm.chat_structured(SYSTEM_SQL, f"TASK: {task}\nSUBTASK: {subtask.description}", QueryRequest)
                args = {"query": resp.parsed.query.strip()}
            elif subtask.tool == "code_execution":
                files = _input_files(subtask, scratchpad)
                code = await _generate_code(task, subtask, files, llm)
                args = {"code": code, "input_files": files}
            else:
                args = subtask.description

            try:
                tool_output = await tool(args)
            except Exception as e:
                tool_error = f"{type(e).__name__}: {e}"
                tool_output = {"error": tool_error}

            # Tools that return a dict with a top-level "error" (sandbox exec, sql, web)
            if tool_error is None and isinstance(tool_output, dict) and tool_output.get("error"):
                tool_error = str(tool_output["error"])

            if tool_error:
                # Remember the bad input so the critic can direct a retry
                scratchpad.setdefault("_tool_failures", {})[subtask.id] = {"args": str(args)[:500], "error": tool_error}

        # Remember the tool output so code_execution deps can mount it
        if tool_output is not None:
            scratchpad[f"_tool_output_{subtask.id}"] = tool_output

    # Keep the LLM context lean: base64 artifact blobs would explode tokens.
    view = tool_output
    if isinstance(view, dict) and view.get("artifacts"):
        view = {**view, "artifacts": [
            {"name": a["name"], "size": a.get("size"), "truncated": a.get("truncated")}
            for a in view["artifacts"]
        ]}
    context = (
        f"TASK: {task}\nSUBTASK: {subtask.description}\n"
        f"SCRATCHPAD: {scratchpad}\nTOOL_OUTPUT: {view}"
    )
    resp = await llm.chat(SYSTEM_EXEC, context)
    return resp.content, tool_output, tool_error, resp.model_dump(include={"tokens_in", "tokens_out", "cost_usd", "latency_ms"})
