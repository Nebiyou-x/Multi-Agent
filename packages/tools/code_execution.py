"""Tool #2: Code Execution.

Runs agent-generated Python inside the ephemeral Docker sandbox. Network is
off for the container, so any data the code needs must arrive as input
files (from http_fetch / web_search / sql in an earlier step). The executor
attaches those files for us.

The tool accepts either a dict or a bare code string:
    code_execution({"code": "...", "input_files": {"data.json": "..."}})
    code_execution("print(sum(range(10)))")
"""

from typing import Dict, Optional, Union

from packages.sandbox import get_sandbox_manager


def _normalize(args: Union[dict, str]) -> dict:
    if isinstance(args, str):
        return {"code": args, "input_files": {}}
    return args or {}


async def code_execution(args: Union[dict, str]) -> dict:
    args = _normalize(args)
    code = args.get("code")
    if not code:
        return {"error": "code_execution requires a 'code' argument"}

    input_files: Dict[str, object] = args.get("input_files") or {}
    manager = await get_sandbox_manager()

    result = await manager.run_code(code, input_files=input_files)
    # Surface the artifacts list up front so the executor can reference them
    # by name in the final answer.
    result["artifact_names"] = [a["name"] for a in result.get("artifacts", [])]
    if result.get("exit_code") not in (0, None) or result.get("timed_out"):
        result["error"] = (
            f"code exited {result.get('exit_code')}"
            + (" (timeout)" if result.get("timed_out") else "")
        )
    return result
