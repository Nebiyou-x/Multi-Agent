---

# Getting Started

Get the agent platform running locally in five steps. You'll build the sandbox environment, launch the services, execute a real-world data task, inspect the execution trace, and generate a report.

> **What you'll build**
>
> A complete local agent execution environment with Docker sandboxing, PostgreSQL persistence, API orchestration, trace visualization, and report generation.

## Prerequisites

Make sure you have the following installed and configured before starting.

| Requirement  | Description                                  |
| ------------ | -------------------------------------------- |
| Docker       | Docker Engine and Docker Compose             |
| Python       | Python 3.12                                  |
| Environment  | Root-level `.env` file                       |
| LLM Provider | API key for your selected provider           |
| Database     | PostgreSQL (provided through Docker Compose) |

### Environment configuration

Create your environment file:

```bash
cp .env.example .env
```

Configure the following variables:

```env
LLM_PROVIDER=openai
LLM_MODEL=your-model
OPENAI_API_KEY=your-api-key

DATABASE_URL=postgresql://agent:agent@localhost:5432/agent_platform
```

Use the API key matching your selected provider:

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Gemini: `GEMINI_API_KEY` or `GOOGLE_API_KEY`

\<aside>
\*\*Optional dependency:\*\* \`TAVILY_API_KEY\` is not required for this walkthrough. The World Bank task uses \`http_fetch\` directly.
\</aside>

---

## 01 — Build the sandbox image

The sandbox image provides an isolated environment for executing agent-generated Python code.

```bash
make sandbox-image
```

This builds `agent-sandbox:latest` from `infra/sandbox-image`.

### What's included?

- Python 3.12-slim
- pandas and numpy
- matplotlib with the headless Agg backend
- Non-root execution user
- Restricted network access and filesystem permissions at runtime

### Verify the sandbox

Run a basic smoke test to verify that the container executes successfully under restricted conditions.

```bash
SNIPPET=$HOME/snippet.py
echo 'print(sum(range(10**7)))' > $SNIPPET

docker run --rm \
  --network none \
  --memory 512m \
  --cpus 0.5 \
  --read-only \
  --tmpfs /tmp \
  -v "$SNIPPET:/main.py:ro" \
  agent-sandbox:latest python /main.py
```

**Expected output:**

```text
49999995000000
```

---

## 02 — Start the application stack

Start all services using Docker Compose:

```bash
docker compose up -d --build
```

### Service endpoints

| Service    | URL                     | Port |
| ---------- | ----------------------- | ---- |
| API        | `http://localhost:8000` | 8000 |
| Trace UI   | `http://localhost:3000` | 3000 |
| PostgreSQL | `localhost:5432`        | 5432 |

### Verify service health

```bash
docker compose ps
```

Wait until PostgreSQL reports a healthy status.

The database health check uses:

```bash
pg_isready -U agent
```

\<aside>
\*\*Important:\*\* The API service mounts \`/var/run/docker.sock\`. This allows the sandbox manager to create and manage sandbox containers through the host Docker daemon. Make sure Docker is running.
\</aside>

---

## 03 — Execute your first agent task

For the first task, we'll use the World Bank API to retrieve Ethiopia's annual inflation data, calculate year-over-year changes, and generate a chart.

The World Bank API is publicly accessible, so no API key is needed.

### Submit the task

```bash
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "task": "Download Ethiopia'\''s annual inflation data from the World Bank API (https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json), compute year-over-year change, and save a line chart to /out/inflation.png"
  }'
```

The API returns the complete run payload, including:

- `run_id` — Unique execution identifier.
- `final_output` — Final response from the agent.
- `steps` — Complete execution history.

Save the returned run ID:

```bash
RUN_ID=<run_id-from-response>
```

### What to expect

Pay attention to these behaviors during execution.

**1. Planning**

The planner typically generates 3–5 steps. A simple fetch-and-plot task may include an additional reasoning step.

The important field is `depends_on`, which determines execution dependencies.

**2. Artifact naming**

The task explicitly requests `/out/inflation.png`.

If the generated script uses a different filename, inspect the `code_execution` step's `tool_output.artifacts` field.

**3. Critic evaluation**

The critic evaluates the agent's output and can request revisions.

- `PASS` — The output satisfies the task.
- `REVISE` — The agent should improve its result.
- Revision attempts are capped by `MAX_REVISIONS` (default: 3).

**4. Sandbox restrictions**

The sandbox intentionally has no network access.

For example, generated code that attempts to use `import requests` to fetch external data will fail with `ModuleNotFoundError` if that dependency or execution path is unavailable.

The expected architecture is to fetch external data through `http_fetch` before passing it to sandboxed code execution.

---

## 04 — Inspect the execution trace

Every agent run stores its execution history, allowing you to inspect the planner, tools, critic, and revision stages.

### Retrieve the full trace

```bash
curl -s http://localhost:8000/runs/$RUN_ID \
  | python3 -m json.tool
```

A successful execution should contain a sequence similar to:

```text
plan
  └── planner

tool_call
  └── http_fetch

tool_call
  └── code_execution

critique
  └── critic

revision
  └── reviser (only when needed)
```

### Retrieve the generated chart

```bash
curl -s -o /tmp/inflation.png \
  http://localhost:8000/artifacts/$RUN_ID/inflation.png
```

Open the generated image:

```bash
open /tmp/inflation.png
```

The same artifact is also available locally:

```text
data/artifacts/<RUN_ID>/inflation.png
```

### Explore the Trace UI

Open the local dashboard:

**[http://localhost:3000](http://localhost:3000)**

The interface allows you to:

- Browse previous agent runs.
- Inspect execution steps.
- Explore the execution tree.
- Review tool calls and outputs.

---

## 05 — Generate an execution report

The platform includes a report generator that converts execution traces into structured reports.

### Prepare the Python environment

Make sure your development dependencies are installed:

```bash
pip install -r requirements-dev.txt
```

### Export the run

```bash
curl -s http://localhost:8000/runs/$RUN_ID -o run.json
```

### Generate the report

```bash
PYTHONPATH=packages \
python -m report trace run.json --out reports/traces/
```

The report generator validates the trace against the frozen schema defined in:

```text
packages/report/schema.py
```

Malformed input will cause validation to fail rather than silently generating an incorrect report.

### Expected report structure

| Step        | Component         | Description                                                      |
| ----------- | ----------------- | ---------------------------------------------------------------- |
| `plan`      | `planner:<model>` | Full execution plan; costs are summed across replanning          |
| `tool_call` | `http_fetch`      | World Bank data retrieval; output truncated to 15,000 characters |
| `tool_call` | `code_execution`  | Generated Python script and output artifacts                     |
| `critique`  | `critic:<model>`  | Evaluation result: PASS or REVISE                                |
| `revision`  | `reviser`         | Replanning and improvement, only when required                   |

---

## Shutdown and cleanup

When you're finished, stop the application stack:

```bash
make down
```

Alternatively:

```bash
docker compose down
```

### Restart later

To rebuild and restart the entire stack:

```bash
docker compose up -d --build
```

**Data persistence:** PostgreSQL data is stored in the `pgdata` Docker volume. Stopping the stack does not remove the persisted database volume.

---

## First-run checklist

Use this checklist to confirm that your local environment is working correctly.

- [ ] Docker image builds successfully.
- [ ] Sandbox smoke test produces the expected output.
- [ ] Docker Compose services start successfully.
- [ ] PostgreSQL reports healthy.
- [ ] API accepts a new agent run.
- [ ] World Bank data is retrieved successfully.
- [ ] Sandbox generates `inflation.png`.
- [ ] Execution trace is accessible through the API.
- [ ] Trace UI displays the execution.
- [ ] Report generator produces a valid report.

**You're ready to go!**

Your local agent platform is now running, and you've completed an end-to-end execution workflow — from task submission and planning to sandbox execution, evaluation, artifact generation, and reporting.
