---
title: Getting Started
summary: Build the sandbox image, start the stack, run the World Bank Ethiopia task, and read the trace back.
order: 1
---

# Getting Started

End-to-end first run: build the sandbox image, start the stack, fire the World
Bank Ethiopia inflation task, read the trace back, and render a report.

## Prerequisites

- Docker + Docker Compose on the host (the API spawns sandbox containers through
  the host Docker daemon, so the daemon must be running)
- Python 3.12 (`.venv/` with `requirements-dev.txt` installed) for the report
  generator
- `.env` at the repo root (copy `.env.example`):
  - `LLM_PROVIDER` / `LLM_MODEL` plus the matching API key
    (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`/`GOOGLE_API_KEY`)
  - `DATABASE_URL` - the compose Postgres (`postgresql://agent:agent@localhost:5432/agent_platform`)
  - `TAVILY_API_KEY` - optional. The demo task works with `http_fetch` alone;
    skip Tavily if you do not have it.

## 1. Build the sandbox image

```bash
make sandbox-image
```

This runs `docker build -t agent-sandbox:latest infra/sandbox-image`. The image
ships Python 3.12-slim, pandas, numpy, matplotlib (headless Agg backend), and a
non-root user. Smoke-test both hardening guarantees:

```bash
SNIPPET=$HOME/snippet.py; echo 'print(sum(range(10**7)))' > $SNIPPET
docker run --rm --network none --memory 512m --cpus 0.5 --read-only \
  --tmpfs /tmp -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py
# expect: 49999999950000000
```

## 2. Start the stack

```bash
docker compose up -d --build
```

Ports: API on 8000, trace UI on 3000, Postgres on 5432. The API service mounts
`/var/run/docker.sock`, so the sandbox manager can spawn
`agent-sandbox:latest` on the host daemon. Wait for Postgres to be healthy:
`docker compose ps` (healthcheck: `pg_isready -U agent`).

## 3. Fire the first task

The World Bank API needs no key, so this task is deterministic without Tavily:

```bash
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"task": "Download Ethiopia'"'"'s annual inflation data from the World Bank API (https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json), compute year-over-year change, and save a line chart to /out/inflation.png"}'
```

The API URL is in the task text on purpose: it removes one planner
guessing-move. The response is the full run payload including `run_id`,
`final_output`, and the step list. Grab the id:

```bash
RUN_ID=<run_id from the response>
```

What to watch on a healthy first run:

- **Plan shape** - the planner emits 3-5 steps; a two-step "fetch + plot" task
  may get a padding reasoning step. `depends_on` is what matters.
- **Artifact naming** - the LLM writes `chart.png` unless the subtask says
  otherwise; here the task says `/out/inflation.png` so the final answer
  matches. If it deviates, check the `code_execution` step's
  `tool_output.artifacts` - names are listed there.
- **Critic strictness** - `REVISE` loops cap at `MAX_REVISIONS` (default 3);
  watch for a run that ends "succeeded" with an unsatisfying answer after the cap.
- **`code_execution` failure is the interesting one** - the sandbox has no
  network by design, so if the generated code writes `import requests` you will
  see a `ModuleNotFoundError` in `stderr` and the critic should route a retry.
  That is the common-trap behavior working as intended.

## 4. Read the trace back

```bash
# full run: steps should show plan -> http_fetch tool_call -> code_execution
# tool_call -> critique -> (maybe revision)
curl -s http://localhost:8000/runs/$RUN_ID | python3 -m json.tool

# the chart, served by the artifacts endpoint
curl -s -o /tmp/inflation.png http://localhost:8000/artifacts/$RUN_ID/inflation.png
open /tmp/inflation.png
```

The same bytes are on the host at `data/artifacts/$RUN_ID/inflation.png`.
The UI at `http://localhost:3000` lists runs and shows the step tree.

## 5. Generate a report

Pull the run's JSON and feed it to the report generator (`packages/` on
`PYTHONPATH`; the generator validates against the frozen schema in
`packages/report/schema.py` and fails loudly on a malformed file):

```bash
curl -s http://localhost:8000/runs/$RUN_ID -o run.json
PYTHONPATH=packages python -m report trace run.json --out reports/traces/
```

The step list in the generated report should look like:

```
plan               planner:<model>          # the full Plan, costs summed if re-planned
tool_call          http_fetch               # World Bank fetch, output truncated to 15000 chars
tool_call          code_execution           # generated script + /out artifacts
critique           critic:<model>           # PASS or REVISE + feedback
revision           reviser                  # only on REVISE, nested under the critique
```

Stop the stack with `make down` (or `docker compose down`). Rebuild everything
later with `docker compose up -d --build` - Postgres data persists in the
`pgdata` volume.
