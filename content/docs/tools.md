---
title: Tools
summary: The four registry tools - http_fetch, web_search, sql_query and code_execution - with inputs, outputs and limits.
order: 3
---

# Tools

Four tools, one registry. `packages/tools/registry.py` is a plain dict:

```python
tool_registry = {
    "http_fetch": http_fetch,
    "code_execution": code_execution,
    "sql_query": sql_query,
    "web_search": web_search,
}
```

The planner picks a tool name per subtask; the executor looks the name up in
this dict, builds the arguments, calls the async function, and returns its
dict. Dispatch is purely by tool name - there is no dynamic registration, and
an unknown name yields an `{"error": "Tool '...' is not registered"}` result,
not an exception.

Two conventions every tool follows:

- **Arguments are built by the executor, not the planner.** The planner only
  names a tool and writes a step description. A small structured LLM call
  (Pydantic model, per-tool) extracts the exact arguments. So the "input
  schema" of a tool is really two things: the Pydantic extraction model in
  `packages/agent_core/executor.py`, and the shape the tool function itself
  accepts.
- **Failures are data, not exceptions.** A failing tool returns
  `{"error": "..."}`; the executor records it in the trace and in
  `scratchpad["_tool_failures"]` so the critic can direct a retry.

The tools form a data pipeline: `http_fetch` / `web_search` / `sql_query`
produce data, `code_execution` consumes it. Sandbox code has no network, so
data for a `code_execution` step always arrives as an input file from an
earlier step (mounted read-only at `/in`).

## http_fetch

Purpose: fetch one specific URL or API endpoint. The workhorse of data tasks.

Input (accepted as a bare string or a dict; the executor passes the extracted
URL, Pydantic model `UrlRequest` in `executor.py`):

```json
{"url": "https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json"}
```

Output shape:

```json
{
  "url": "https://...",
  "status": 200,
  "content": "...",
  "truncated": false
}
```

Limits and behavior:

- httpx with a 10s timeout and redirect following.
- `content` is truncated to 15000 characters; `truncated` is true when the
  body was longer. This is deliberate - it prevents a big response from
  exploding the next LLM call's context.
- No API key needed. Non-`http(s)` URLs raise before the request.

## web_search

Purpose: find sources for a question when no URL is known yet. Wraps the
Tavily API; results are cached on disk so replanned queries do not burn API
calls.

Input (Pydantic model `QueryRequest` in `executor.py`: `{query: str}`; the
executor adds `max_results`):

```json
{"query": "Ethiopia annual inflation rate World Bank", "max_results": 5}
```

Output shape:

```json
{
  "query": "...",
  "results": [{"title": "...", "url": "...", "snippet": "..."}],
  "source": "tavily",
  "cached": false
}
```

Limits and behavior:

- **Requires `TAVILY_API_KEY`** in the environment. Without it the tool
  returns `{"error": "TAVILY_API_KEY is not set - web_search is unavailable"}`
  - a clean error the critic can act on, not a crash.
- `max_results` defaults to 5 (the executor hardcodes it at 5).
- Cache: `WEB_SEARCH_CACHE_DIR` (default `.cache/web_search`),
  `WEB_SEARCH_CACHE_TTL` seconds (default 24h). A cache hit returns
  `"cached": true`.

## sql_query

Purpose: read-only queries against the analytics Postgres. Deliberately a
much simpler sandbox than code execution: one statement per call, in a
read-only session that is never committed.

Input (Pydantic model `QueryRequest`: `{query: str}`; the executor passes a
read-only SELECT extracted from the step description):

```json
{"query": "SELECT country, year, value FROM data.inflation WHERE country = 'Ethiopia'"}
```

Output shape:

```json
{
  "columns": ["country", "year", "value"],
  "rows": [["Ethiopia", 2023, 5.3]],
  "row_count": 1,
  "truncated": false,
  "limit": 1000
}
```

Limits and behavior:

- **Requires `DATABASE_URL`** (set for the compose Postgres). Without it:
  `{"error": "DATABASE_URL is not set - sql_query cannot connect"}`.
- Connection opens with `readonly=True` and `connect_timeout=10`; the session
  is pinned to `search_path = public, <SQL_ALLOWED_SCHEMAS>` (default
  `data`), so it cannot reach other schemas. `statement_timeout` is
  `SQL_TIMEOUT_S` (default 15s); `SQL_MAX_ROWS` (default 1000) caps fetched
  rows - `truncated` is true when the cap was hit.
- Writes are rejected by Postgres (`read-only transaction`) and surfaced as
  a clean `{"error": "write rejected - this connection is read-only"}`.

## code_execution

Purpose: write and run LLM-generated Python in the Docker sandbox. This is
where charts, math, and data wrangling happen.

Input (a dict, or a bare code string - both accepted):

```json
{
  "code": "import pandas as pd\nrows = pd.read_json('/in/s1.json')...\nfig.savefig('/out/inflation.png')",
  "input_files": {"s1.json": {"url": "...", "content": "..."}}
}
```

The `code` field is itself LLM-generated: for a `code_execution` subtask the
executor runs a code-writing LLM call first (see `SYSTEM_CODE` in
`executor.py` - no network, inputs at `/in`, writable `/out`, pandas/numpy/
matplotlib available). The output shape, as returned to the trace:

```json
{
  "exit_code": 0,
  "timed_out": false,
  "stdout": "saved /out/inflation.png\n",
  "stderr": "",
  "artifacts": [{"name": "inflation.png", "size": 48213, "content_b64": "...", "truncated": false}],
  "artifact_names": ["inflation.png"],
  "warnings": [],
  "duration_ms": 4123,
  "code": "..."
}
```

(`artifact_names` and `code` are attached by the tool wrapper; the executor
also keeps the generated source on the trace step so the critic can
reference it.)

Limits and behavior:

- Runs inside the Docker sandbox with `--network none`: `import requests`
  or `socket` will fail at runtime by design. The code's data must come in
  via `input_files`.
- Inputs are mounted read-only under `/in/<name>`: dict/list values are
  written as JSON (`<name>.json`), plain strings verbatim (`<name>.txt`).
  File names must be flat basenames - path traversal is rejected.
- Artifacts written under `/out` are collected, base64-inlined into the
  result with size caps (`SANDBOX_ARTIFACT_FILE_CAP` default 512000 bytes per
  file, `SANDBOX_ARTIFACT_CAP` default 1000000 total; beyond the cap the
  entry carries name + size and `truncated: true`).
- Wall-clock timeout `SANDBOX_TIMEOUT` seconds (default 30); 512m memory,
  0.5 CPU. On timeout the container is killed and destroyed; the result
  carries `timed_out: true` and an `error` string.
- The whole isolation model is in `docs/sandbox.md`.
