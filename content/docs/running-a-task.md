---
title: Running a Task
summary: POST a task, replay it on another provider or model, and see where traces and artifacts land.
order: 2
---

# Running a Task

The whole system is one endpoint. Start the stack (`docker compose up -d --build`
after `make sandbox-image`), then POST a task. Everything else - traces,
artifacts, replay - hangs off the run id that comes back.

## POST /runs

```bash
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"task": "<task text>", "provider": "openai", "model": "gpt-4o-mini"}'
```

Payload shape (`TaskRequest` in `apps/api/main.py`):

| field     | type        | required | notes |
|-----------|-------------|----------|-------|
| `task`    | `str`       | yes      | free-form task text; the planner decomposes it |
| `provider`| `str \| null` | no     | one of `openai`, `anthropic`, `gemini`; defaults to `LLM_PROVIDER` env (`openai`) |
| `model`   | `str \| null` | no     | any model from the provider's pricing table in `packages/agent_core/llm.py`; defaults to `LLM_MODEL` env (`gpt-4o-mini`) |

The request is blocking: the API runs the full plan-execute-critique pipeline
in-process and returns the finished run. The response is the full run payload:
`run_id`, `task`, `status` (`succeeded` or `failed`), `provider`, `model`,
`created_at`, `final_output` (`{"answer", "artifacts"}`), and the complete
`steps` list. `final_output.artifacts` lists paths like
`/artifacts/<run_id>/inflation.png` you can fetch from the same API.

Tip: `GET /config` lists which providers/models the API knows and which API keys
are set, so you can pick a valid `provider`/`model` pair before posting.

## Replay a task with a different provider/model

A replay is just another `POST /runs` with the same task text and a different
provider/model. The orchestrator builds a fresh `LLMClient` when either override
is set, so the entire pipeline - planner, executor, critic, revision - runs on
the new model; nothing is shared with the original run.

```bash
# original run (defaults)
curl -s -X POST http://localhost:8000/runs -H 'Content-Type: application/json' \
  -d '{"task": "<task text>"}'

# replay the same task on Claude
curl -s -X POST http://localhost:8000/runs -H 'Content-Type: application/json' \
  -d '{"task": "<task text>", "provider": "anthropic", "model": "claude-3-5-sonnet-20240620"}'
```

Each run records its own `provider` and `model` on the `runs` row and on every
step, so `GET /runs` shows both side by side. The trace UI's compare page
(`apps/trace-ui/app/compare/[a]/[b]/page.tsx`) is the UI-side view of two
replays of one task.

Caveats:

- A replay is a new run, not a resumed one: new `run_id`, new trace, new
  artifacts directory.
- Cost is real and cumulative. Two replays of a charting task on a large model
  can be several times the cost of the default.
- Structured-output behavior differs per provider (OpenAI JSON schema,
  Anthropic forced tool call, Gemini native schema - see
  `packages/agent_core/llm.py`), so "replay the same task" is same task,
  not identical outputs.

## Where traces and artifacts land

- **Traces**: Postgres, one row in `runs`, one row in `steps` per step
  (`infra/postgres/init.sql`). Served by `GET /runs/{run_id}` as JSON.
- **Artifacts**: on the host at `data/artifacts/<run_id>/<name>`,
  bind-mounted into the API container (`ARTIFACT_DIR=/app/data/artifacts`).
  After a run, the API decodes the base64 artifact blobs from the trace and
  writes them here; large or truncated artifacts (name + size only, no
  `content_b64`) are skipped.
- Served back via `GET /artifacts/{run_id}/{name}` (path traversal guarded;
  only `<run_id>/<name>` inside `ARTIFACT_DIR` resolves).

`data/artifacts/` is gitignored (`.gitignore`: `data/artifacts/` with a
`.gitkeep`). It is a cache of the last runs, not durable storage - the durable
record of what a run produced is the trace in Postgres plus
`final_output.artifacts`.

## Pull a run's JSON for the report generator

The report generator validates against the frozen `TraceRun` schema in
`packages/report/schema.py`, so the input must have that shape: `run_id`,
`task`, `status` (`succeeded|failed|timeout`), `steps` with `step_id`,
`type`, `input`, `output`, `tokens {in,out}`, `cost_usd`, `latency_ms`,
`parent_step_id` optional.

Two sources:

1. **From the API** - `curl -s http://localhost:8000/runs/$RUN_ID -o run.json`.
   The API payload is close to the frozen contract but not byte-identical, and
   the contract forbids extra fields (`extra="forbid"`): the payload carries
   `created_at` where the contract expects `started_at`/`finished_at`
   (both optional). Drop or rename `created_at` before loading - `ReportError`
   names the offending field if you get it wrong, and that is the expected
   workflow. Step objects match the contract as-is.
2. **From Postgres directly** - the `steps` table keeps `input`/`output` as
   JSONB; assemble `{"run_id", "task", "status", "steps":[...]}` by joining
   `runs` and `steps` ordered by `seq`. This is the shape the API itself
   returns, since `GET /runs/{run_id}` does exactly that join.

Then render:

```bash
PYTHONPATH=packages python -m report trace run.json --out reports/traces/
```

The generator writes `reports/traces/<stem>.md` and `<stem>.html` (plus
decoded artifact images under `assets/<stem>/`), verifies determinism, and
is the committed-artifacts location from `docs/design-decisions.md`
ADR-005.

Note: the report subcommands import `jinja2` and `matplotlib`, which are in
the local `.venv` but not yet declared in any requirements file - run
them from that environment (see `docs/roadmap.md`).
