

Perfect timing — here's the exact runbook so you can execute it end-to-end without me touching anything.

## 1. Prereqs (env)

In `.env`:
- `OPENAI_API_KEY` (or whichever `LLM_PROVIDER`/`LLM_MODEL` you're using)
- `TAVILY_API_KEY` — optional. The World Bank API needs no key, so the planner can get by with `http_fetch` alone. Skip Tavily if you don't have it.
- `DATABASE_URL` pointing at the compose postgres (already there from `.env`)

## 2. Build + smoke-test the sandbox image (the "Done when")

```bash
make sandbox-image          # docker build -t agent-sandbox:latest infra/sandbox-image
```

Then the two "Done when" probes:

```bash
# 1) works under full hardening
SNIPPET=$HOME/snippet.py; echo 'print(sum(range(10**7)))' > $SNIPPET
docker run --rm --network none --memory 512m --cpus 0.5 --read-only \
  --tmpfs /tmp -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py
# expect: 49999999950000000

# 2) hostile code fails safely
echo "import os; os.system('rm -rf /') ; import socket; socket.socket()" > $SNIPPET
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py
# rm -rf / will "succeed" as a no-op on a read-only rootfs (you can verify with
# read-only / after: cat /bin/sh still exists); the socket call raises
# PermissionError/ConnectionRefused because --network none.
```

Note the `--tmpfs /tmp` — the Dockerfile sets `PYTHONDONTWRITEBYTECODE=1` and `MPLCONFIGDIR=/tmp`, so a read-only root without a `/tmp` mount would fail on matplotlib config.

## 3. Boot the stack

```bash
docker compose up -d --build
```

The api service now has the docker socket mounted, so the manager can spawn sandbox containers on the host daemon and `agent-sandbox:latest` is visible to it.

## 4. Fire the milestone task

```bash
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"task": "Download Ethiopia'"'"'s annual inflation data from the World Bank API (https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json), compute year-over-year change, and save a line chart to /out/inflation.png"}'
```

I included the API URL in the task text on purpose — it removes one planner guessing-move and makes the run deterministic.

## 5. Verify the trace + artifact

```bash
RUN_ID=<run_id from the response>

# steps should show: plan -> http_fetch tool_call -> code_execution tool_call
# -> critique -> (maybe revision)
curl -s http://localhost:8000/runs/$RUN_ID | python3 -m json.tool

# the chart, served by the new endpoint:
curl -s -o /tmp/inflation.png http://localhost:8000/artifacts/$RUN_ID/inflation.png
open /tmp/inflation.png
```

And on the host: the bytes are also written to `data/artifacts/$RUN_ID/inflation.png`.

## What I'd watch for on the first run

- **Plan shape** — the planner needs ≥3 steps; a 2-step "fetch + plot" might get padded with a reasoning step. That's fine, `depends_on` is what matters.
- **Artifact naming** — the LLM writes `chart.png` unless the subtask says otherwise; I phrased the task with `/out/inflation.png` so the reference in the final answer matches. If the model deviates, check the `code_execution` step's `tool_output.artifacts` in the trace — the executor summary lists actual names.
- **Critic strictness** — if it REVISEs, the loop caps at `MAX_REVISIONS` (default 3); watch the run not silently end "succeeded" with an unsatisfying answer.
- **`code_execution` failure is the interesting one** — network is off by design, so if the LLM writes `import requests` you'll see a `ModuleNotFoundError` in `stderr` and the critic should route a retry. That's the common-trap behavior working as intended.

Run it and paste me the output (or the failures) — if the plan/execution shape comes out wrong I'll adjust the planner or code-gen prompts, which is the most likely first-run fix.

Perfect timing — here's the exact runbook so you can execute it end-to-end without me touching anything.

## 1. Prereqs (env)

In `.env`:
- `OPENAI_API_KEY` (or whichever `LLM_PROVIDER`/`LLM_MODEL` you're using)
- `TAVILY_API_KEY` — optional. The World Bank API needs no key, so the planner can get by with `http_fetch` alone. Skip Tavily if you don't have it.
- `DATABASE_URL` pointing at the compose postgres (already there from `.env`)

## 2. Build + smoke-test the sandbox image (the "Done when")

```bash
make sandbox-image          # docker build -t agent-sandbox:latest infra/sandbox-image
```

Then the two "Done when" probes:

```bash
# 1) works under full hardening
SNIPPET=$HOME/snippet.py; echo 'print(sum(range(10**7)))' > $SNIPPET
docker run --rm --network none --memory 512m --cpus 0.5 --read-only \
  --tmpfs /tmp -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py
# expect: 49999999950000000

# 2) hostile code fails safely
echo "import os; os.system('rm -rf /') ; import socket; socket.socket()" > $SNIPPET
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py
# rm -rf / will "succeed" as a no-op on a read-only rootfs (you can verify with
# read-only / after: cat /bin/sh still exists); the socket call raises
# PermissionError/ConnectionRefused because --network none.
```

Note the `--tmpfs /tmp` — the Dockerfile sets `PYTHONDONTWRITEBYTECODE=1` and `MPLCONFIGDIR=/tmp`, so a read-only root without a `/tmp` mount would fail on matplotlib config.

## 3. Boot the stack

```bash
docker compose up -d --build
```

The api service now has the docker socket mounted, so the manager can spawn sandbox containers on the host daemon and `agent-sandbox:latest` is visible to it.

## 4. Fire the milestone task

```bash
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"task": "Download Ethiopia'"'"'s annual inflation data from the World Bank API (https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json), compute year-over-year change, and save a line chart to /out/inflation.png"}'
```

I included the API URL in the task text on purpose — it removes one planner guessing-move and makes the run deterministic.

## 5. Verify the trace + artifact

```bash
RUN_ID=<run_id from the response>

# steps should show: plan -> http_fetch tool_call -> code_execution tool_call
# -> critique -> (maybe revision)
curl -s http://localhost:8000/runs/$RUN_ID | python3 -m json.tool

# the chart, served by the new endpoint:
curl -s -o /tmp/inflation.png http://localhost:8000/artifacts/$RUN_ID/inflation.png
open /tmp/inflation.png
```

And on the host: the bytes are also written to `data/artifacts/$RUN_ID/inflation.png`.

## What I'd watch for on the first run

- **Plan shape** — the planner needs ≥3 steps; a 2-step "fetch + plot" might get padded with a reasoning step. That's fine, `depends_on` is what matters.
- **Artifact naming** — the LLM writes `chart.png` unless the subtask says otherwise; I phrased the task with `/out/inflation.png` so the reference in the final answer matches. If the model deviates, check the `code_execution` step's `tool_output.artifacts` in the trace — the executor summary lists actual names.
- **Critic strictness** — if it REVISEs, the loop caps at `MAX_REVISIONS` (default 3); watch the run not silently end "succeeded" with an unsatisfying answer.
- **`code_execution` failure is the interesting one** — network is off by design, so if the LLM writes `import requests` you'll see a `ModuleNotFoundError` in `stderr` and the critic should route a retry. That's the common-trap behavior working as intended.

Run it and paste me the output (or the failures) — if the plan/execution shape comes out wrong I'll adjust the planner or code-gen prompts, which is the most likely first-run fix.