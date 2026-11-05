# Multi-Agent Execution Platform

A production-ready system for autonomous agent execution with sandboxed code execution, execution tracing, and comprehensive reporting. Agents plan complex tasks, execute code in isolated Docker containers, and generate artifacts—all with complete visibility into every step.

## Overview

This platform provides a complete infrastructure for running autonomous AI agents with a focus on safety, observability, and reproducibility. It combines:

- **Planning**: Multi-step task planning with dependency tracking
- **Execution**: Tool-based agent reasoning with support for multiple LLM providers
- **Sandboxing**: Isolated Docker-based execution environment for generated code
- **Evaluation**: Automated critique/revision loops plus deterministic golden-task scoring
- **Visualization**: Trace UI for runs and an evaluation dashboard with regression comparison
- **Reporting**: Structured reports from execution traces with schema validation
- **Performance Tracking**: Config-hashed eval runs, category breakdowns, and PASS→FAIL detection

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Server (FastAPI)                       │
│  /runs  /artifacts  /traces  [Orchestration & State Management] │
└────────────────┬────────────────────────────────┬───────────────┘
                 │                                │
        ┌────────▼────────┐            ┌──────────▼──────────┐
        │  Agent Executor │            │    Sandbox Manager  │
        │  ┌───────────┐  │            │  (Docker Socket)    │
        │  │ Planner   │  │            │  ┌──────────────┐   │
        │  ├───────────┤  │            │  │ agent-sandbox│   │
        │  │ LLM Agent │  │            │  │ (isolated)   │   │
        │  ├───────────┤  │            │  └──────────────┘   │
        │  │ Critic    │  │            │                     │
        │  ├───────────┤  │            └─────────────────────┘
        │  │ Tools     │  │                     ▲
        │  │ • http    │  │                     │
        │  │ • exec    │  │──────────────────────┘
        │  │ • etc     │  │
        │  └───────────┘  │
        └─────────────────┘
                 │
        ┌────────┴───────────────┐
        │                        │
   ┌────▼────┐            ┌──────▼─────┐
   │PostgreSQL│            │   Redis    │
   │          │            │            │
   │• Runs    │            │• Queues    │
   │• Traces  │            │• Cache     │
   │• Artifacts           └────────────┘
   └──────────┘
        │
   ┌────▼──────────────────┐
   │  Trace UI (Next.js)   │
   │  - Run Browser        │
   │  - Tree Visualization │
   │  - Trace Inspector    │
   │  - Eval Dashboard     │
   └───────────────────────┘
```

Evaluation path, independent of the run-time request flow:

```
datasets/golden/tasks.jsonl
          │
          ▼
   EvalRunner (async, max_parallel)
          │
          ▼
   7 deterministic scorers
          │
          ▼
 data/eval_results/eval_*.json
          │
          ▼
 Trace UI /evals ──► /evals/compare/{a}/{b}
```

## Tech Stack

| Component        | Technology                | Purpose                          |
| :--------------- | :------------------------ | :------------------------------- |
| **API Server**   | Python, FastAPI           | Task orchestration & REST API    |
| **Agent Logic**  | Python                    | Planning, execution, critique    |
| **Sandbox**      | Docker, Python 3.12       | Isolated code execution          |
| **Frontend**     | TypeScript, Next.js, React | Execution visualization & UX     |
| **Database**     | PostgreSQL 16              | Run history & trace persistence  |
| **Cache/Queue**  | Redis 7                   | Session state & task queuing     |
| **Evaluation**   | Python asyncio, JSON Schema | Golden tasks, scoring, regressions |
| **LLM Providers**| OpenAI, Anthropic, Gemini | AI reasoning & planning          |

## Key Components

### Agent Core (`packages/agent_core`)

The core reasoning engine:

- **Planner** (`planner.py`): Breaks down tasks into multi-step execution plans with dependency tracking
- **Executor** (`executor.py`): Orchestrates plan execution, manages tool calls, and handles state transitions
- **LLM Interface** (`llm.py`): Unified API for multiple LLM providers with streaming and token accounting
- **Critic** (`critic.py`): Evaluates execution results and determines if revisions are needed

### Sandbox (`packages/sandbox`)

Isolated execution environment:

- Runs untrusted agent-generated Python code
- Docker-based with strict resource limits (memory, CPU, filesystem)
- Network-restricted execution by default
- Non-root user with read-only filesystem except `/tmp`
- Built from `infra/sandbox-image` with minimal, hardened dependencies

### Tools (`packages/tools`)

Agent-accessible tools:

- **http_fetch**: Fetch data from external APIs and web endpoints
- **code_execution**: Execute Python code in the sandboxed environment
- **file_operations**: Read/write to artifact storage
- Additional tools configured per use case

### Trace System (`packages/trace`)

Execution history & schemas:

- Structured representation of agent execution steps
- Dependency tracking between steps
- Tool call history with inputs/outputs
- Artifact references and locations
- Cost accounting (tokens, API calls)

### Report Generator (`packages/report`)

Converts execution traces to structured reports:

- Schema validation ensures trace correctness
- HTML/markdown report templates
- Cost analysis and performance metrics
- Evaluation summaries and critique results
- Extensible template system

### API Server (`apps/api`)

FastAPI backend:

- **POST /runs**: Submit new tasks for agent execution
- **GET /runs/{run_id}**: Retrieve execution trace
- **GET /artifacts/{run_id}/{name}**: Download generated artifacts
- Real-time status updates via WebSocket or polling
- Sandbox manager integration via Docker socket

### Trace UI (`apps/trace-ui`)

Next.js frontend dashboard:

- Browse and filter previous runs
- Interactive trace tree visualization
- Step-by-step execution inspector
- Tool call details with syntax highlighting
- Real-time cost calculation
- Artifact preview and download
- Evaluation dashboard at `/evals`: committed run reports, category breakdowns, per-task scorer details, and run-to-run regression comparison

### Evaluation Framework (`packages/eval`)

Deterministic performance tracking and regression detection:

- **Golden Dataset** (`golden.py`): 9 tasks across data analysis, multi-hop research, and code execution, stored in `datasets/golden/tasks.jsonl`
- **Deterministic Scorers** (`scorers.py`): 7 scorers plus aliases for task-specific check names; schema validation always runs first
- **Pass Rule**: a task passes only when its output validates against the task schema and at least 80% of the remaining checks pass. Score is the mean of the schema score and the check pass fraction
- **Parallel Executor** (`runner.py`): async task execution with `max_parallel`, config hashing, per-task metrics, and JSON/Markdown reports
- **Regression Detection**: compares any two runs and flags PASS→FAIL regressions plus FAIL→PASS improvements
- **Persistence**: reports are written to `data/eval_results/` and rendered by the Trace UI
- **CLI Tool** (`scripts/eval.py`): `init`, `run`, `list`, `show`, and `compare` commands

The committed runs in `data/eval_results/` were produced with the deterministic mock executor in `runner.run_task()`. They validate the scoring, reporting, and regression plumbing; wire `run_task()` to `packages.agent_core.executor` for model-specific results.

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12
- LLM API key (OpenAI, Anthropic, or Gemini)
- ~2GB disk space for Docker images and data

### Quick Start

1. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your LLM provider credentials
   ```

2. **Build sandbox image**
   ```bash
   make sandbox-image
   ```

3. **Start services**
   ```bash
   docker compose up -d --build
   ```

4. **Submit a task**
   ```bash
   curl -X POST http://localhost:8000/runs \
     -H 'Content-Type: application/json' \
     -d '{"task": "Your task description here"}'
   ```

5. **View results**
   - API trace: `http://localhost:8000/runs/{run_id}`
   - Dashboard: `http://localhost:3000`

For detailed walkthrough with a real example, see [Getting Started Guide](content/docs/getting-started.md).

## Project Structure

```
Multi-Agent/
├── apps/
│   ├── api/                    # FastAPI backend server
│   │   ├── main.py             # Entry point, route definitions
│   │   ├── models/             # Pydantic models for API contracts
│   │   ├── routes/             # API endpoint handlers
│   │   └── Dockerfile          # API container build
│   │
│   └── trace-ui/               # Next.js frontend dashboard
│       ├── app/                # App router: /traces, /evals, /docs
│       ├── components/         # React components
│       ├── lib/                # API client, eval report loader, diffing
│       ├── reports/            # Committed trace + eval reports for static views
│       └── Dockerfile          # Trace UI container build
│
├── packages/                   # Shared Python libraries
│   ├── agent_core/             # Core agent reasoning
│   │   ├── planner.py
│   │   ├── executor.py
│   │   ├── llm.py
│   │   └── critic.py
│   │
│   ├── eval/                   # Performance evaluation framework
│   │   ├── golden.py           # Golden dataset (9 deterministic tasks)
│   │   ├── scorers.py          # 7 deterministic scorers + aliases
│   │   └── runner.py           # Parallel executor + regression tracking
│   │
│   ├── sandbox/                # Sandbox execution orchestration
│   │   ├── manager.py          # Docker sandbox manager
│   │   └── executor.py
│   │
│   ├── tools/                  # Agent tools
│   │   ├── http_fetch/         # HTTP client tool
│   │   ├── code_execution/     # Sandbox code runner
│   │   └── ...
│   │
│   ├── trace/                  # Trace data structures
│   │   └── schemas.py
│   │
│   └── report/                 # Report generation
│       ├── schema.py           # Validation schemas
│       ├── trace_report.py     # Report builder
│       ├── cli.py              # CLI entry point
│       └── templates/          # HTML/Markdown templates
│
├── infra/
│   ├── postgres/               # PostgreSQL initialization
│   │   └── init.sql            # Schema setup
│   │
│   └── sandbox-image/          # Docker image for agent code execution
│       ├── Dockerfile
│       └── requirements.txt
│
├── tests/                      # Test suites
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── datasets/                   # Deterministic evaluation inputs
│   └── golden/tasks.jsonl      # 9 golden tasks with schemas + checks
│
├── content/docs/               # Documentation
│   ├── getting-started.md      # Complete setup walkthrough
│   ├── evaluation.md           # Evaluation reference
│   └── eval-quickstart.md      # 5-minute evaluation guide
│
├── scripts/                    # Utility scripts
│   └── eval.py                 # Evaluation CLI (init/run/list/show/compare)
├── data/                       # Runtime data
│   ├── artifacts/              # Generated artifacts per run
│   └── eval_results/           # Eval JSON + Markdown reports
├── docker-compose.yml          # Service orchestration
├── Makefile                    # Build & development tasks
└── requirements-dev.txt        # Development dependencies
```

## Execution Flow

```
1. Task Submission
   └─→ POST /runs with task description

2. Planning Phase
   └─→ Planner LLM creates multi-step plan with dependencies
       └─→ Each step has tools, inputs, depends_on list

3. Execution Loop
   ├─→ Executor selects next executable step
   ├─→ Tool invocation (http_fetch, code_execution, etc)
   ├─→ Result captured and stored
   └─→ Repeat until plan complete or max steps reached

4. Critique Phase
   └─→ Critic LLM evaluates final output
       ├─→ PASS: Execution complete
       └─→ REVISE: Request replanning and retry (up to MAX_REVISIONS)

5. Artifact Collection
   └─→ Generated files stored in data/artifacts/{run_id}/

6. Trace Persistence
   └─→ Full execution history saved to PostgreSQL
       ├─→ Accessible via /runs/{run_id}
       └─→ Visualizable in Trace UI
```

## Key Concepts

### Runs
A single task execution from submission through completion. Each run contains:
- Task description
- Execution plan
- Step-by-step execution trace
- Critique results
- Generated artifacts
- Cost metrics

### Traces
Structured record of every step in execution:
- Plan steps with dependencies
- Tool calls with parameters and results
- Artifacts generated
- Token usage and API costs
- Timing information

### Sandbox
Isolated Docker environment for executing agent-generated code:
- No network access (unless explicitly provided)
- Memory and CPU limits
- Read-only root filesystem
- Temporary `/tmp` for scratch space
- Artifact output directory
- Non-root execution user

### Critic
Automated evaluation system:
- Reviews agent output against original task
- Returns PASS, REVISE, or FAIL verdict
- Provides reasoning and improvement suggestions
- Capped revision attempts (default: 3)

### Artifacts
Files generated during execution:
- Charts, images, data files
- Stored in `data/artifacts/{run_id}/`
- Served via `/artifacts/{run_id}/{name}`
- Persisted across service restarts

## Evaluation

The evaluation framework measures agent behavior against a fixed golden dataset and makes regressions visible in CI and in the Trace UI.

### Method

- **Golden dataset**: 9 tasks in `datasets/golden/tasks.jsonl`, three per category:
  - **Data analysis**: fetch, compute, chart, and validate
  - **Multi-hop research**: search, fetch, synthesize, cite
  - **Code execution**: generate code, run tests, validate files
- **Deterministic scoring**: every task defines a JSON schema, a list of checks, and optionally a reference answer.
- **Pass rule**: `schema_valid` must pass, at least 80% of the remaining checks must pass, and the task score is the mean of the schema score and the check pass fraction.
- **Config identity**: a SHA-256 hash of the run configuration groups runs and makes comparisons reproducible.
- **Regression detection**: compare any two runs to flag `PASS → FAIL` regressions, `FAIL → PASS` improvements, and score/cost/latency deltas.

| Scorer | What it validates |
| :----- | :---------------- |
| `schema_valid` | Output conforms to the task's JSON Schema |
| `numeric_tolerance` | Reference numbers match within ±5% |
| `exact_match` | Exact string or structure equality |
| `code_passes_tests` | `test_results.passed / total ≥ 80%` |
| `file_exists` | Expected artifact files were generated |
| `citation_quality` | URLs or citation markers are present |
| `output_length` | Output meets the minimum length threshold |

Task-specific check names (`numeric_exact`, `quartile_order`, `source_count`, `output_file_valid`, etc.) resolve through aliases in `packages/eval/scorers.py`.

### Committed results

Reports live in `data/eval_results/` and are rendered in the Trace UI at `/evals`.

| Run | Config | Passed | Pass rate | Total cost | Avg latency |
| :-- | :----- | -----: | --------: | ---------: | ----------: |
| `eval_d3bd3327_20261105_105605` | `model=gpt-4, version=1.0` | 1/9 | 11.1% | $0.0450 | 675ms |
| `eval_4b4b83c1_20261105_105608` | `model=claude-opus, version=2.0` | 1/9 | 11.1% | $0.0450 | 507ms |
| `eval_76378ca5_20261105_105201` | `gpt-4, 1.0, temperature=0.7` | 1/9 | 11.1% | $0.0450 | 384ms |
| `eval_32fac52f_20261105_105202` | `claude-opus, 2.0, temperature=0.5` | 1/9 | 11.1% | $0.0450 | 318ms |
| `eval_ab416ce3_20261105_105501` | `test=quick` | 1/9 | 11.1% | $0.0450 | 399ms |

By category, every committed run reports the same profile:

| Category | Tasks | Passed | Avg score |
| :------- | ----: | -----: | --------: |
| Data analysis | 3 | 1 | 0.28 |
| Multi-hop research | 3 | 0 | 0.22 |
| Code execution | 3 | 0 | 0.00 |

> **Current scope:** `EvalRunner.run_task()` still returns deterministic mock outputs. Identical scores across configs are expected and mean the harness, scorers, reporting, and regression detection are working—not that the models are equivalent. Wire `run_task()` to `packages.agent_core.executor` before using these numbers for model selection.

### Reproduce and compare

```bash
# Initialize the golden dataset (one time)
make eval-init

# Run the full evaluation and write JSON + Markdown reports
make eval-run
# or: python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown

# List committed runs
make eval-list

# Compare two runs; exits non-zero when a regression is found
python scripts/eval.py compare --run1 <run1_id> --run2 <run2_id> --markdown
```

Open `/evals` in the Trace UI to inspect per-task scorer details, or `/evals/compare/{run_a}/{run_b}` to render the same regression analysis.

## Development

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=packages --cov=apps

# Specific test file
pytest tests/unit/test_planner.py
```

### Running Evaluations

```bash
# Initialize golden dataset (one time)
make eval-init

# Run evaluation against agent config
python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown
# or simply: make eval-run

# List all evaluation runs
make eval-list

# Compare two runs and detect regressions
make eval-compare RUN1=<run1_id> RUN2=<run2_id>
# or: python scripts/eval.py compare --run1 <run1_id> --run2 <run2_id> --markdown
```

Results are written to `data/eval_results/` and can be inspected in the Trace UI at `/evals` and `/evals/compare/{a}/{b}`.

### Local Development

```bash
# Start services
docker compose up -d

# Rebuild API after changes
docker compose restart api

# View logs
docker compose logs -f api
docker compose logs -f trace-ui
```

### Database

- Initialized via `infra/postgres/init.sql`
- Migrations can be added to that file
- Persisted in `pgdata` Docker volume
- Connect: `psql postgresql://agent:agent@localhost:5432/agent_platform`

## Configuration

Environment variables (`.env` file):

```env
# LLM Provider
LLM_PROVIDER=openai              # openai, anthropic, gemini
LLM_MODEL=gpt-4                  # Model identifier
OPENAI_API_KEY=sk-...            # For OpenAI
ANTHROPIC_API_KEY=sk-ant-...     # For Anthropic
GOOGLE_API_KEY=...               # For Gemini

# Database
DATABASE_URL=postgresql://agent:agent@localhost:5432/agent_platform

# Sandbox
MAX_MEMORY_MB=512                # Memory limit per sandbox
MAX_CPU=0.5                      # CPU limit (cores)
SANDBOX_TIMEOUT_SECONDS=60       # Execution timeout

# Execution
MAX_REVISIONS=3                  # Critic revision attempts
MAX_STEPS=20                     # Maximum execution steps
```

## Performance & Limits

- **Sandbox memory**: 512MB default (configurable)
- **Sandbox CPU**: 0.5 cores default
- **Execution timeout**: 60s per sandbox invocation
- **Max execution steps**: 20 per run
- **Max revision attempts**: 3 per run
- **Trace output**: Truncated to 15,000 characters for large results
- **Evaluation tasks**: 9 golden tasks across 3 categories
- **Evaluation parallelism**: 4 tasks by default (`max_parallel`)
- **Evaluation runtime**: ~1-2s with the mock executor; real model latency dominates after integration

## Troubleshooting

### Sandbox fails with `ModuleNotFoundError`
The sandbox has a minimal Python environment. External packages must be installed in `infra/sandbox-image/requirements.txt` and the image rebuilt:
```bash
# Edit infra/sandbox-image/requirements.txt
make sandbox-image
docker compose restart api
```

### PostgreSQL won't start
Check if port 5432 is in use or if the `pgdata` volume is corrupted:
```bash
docker compose down -v  # Remove volume
docker compose up postgres  # Rebuild
```

### API can't reach Docker daemon
Verify the socket is mounted:
```bash
docker compose exec api ls -l /var/run/docker.sock
```

### Out of memory during execution
Increase sandbox memory limit:
```bash
# In .env
MAX_MEMORY_MB=1024
```

## Contributing

1. Create a feature branch from `main`
2. Make changes and write tests
3. Run test suite: `pytest`
4. Verify type checking: `mypy packages apps`
5. Create a pull request with description of changes

## Resources

- [Getting Started Guide](content/docs/getting-started.md) — Complete setup walkthrough with real example
- [Evaluation Framework](content/docs/evaluation.md) — Golden dataset, scorers, regression tracking
- [Evaluation Quick Start](content/docs/eval-quickstart.md) — 5-minute guide to running evals
- [API Documentation](docs/api.md) — Endpoint specifications
- [Architecture Deep Dive](docs/architecture.md) — System design details
- [Tool Development Guide](docs/tools.md) — Creating custom agent tools



**Built for autonomous execution with safety, observability, and precision.**
