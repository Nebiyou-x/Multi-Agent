# Multi-Agent Execution Platform

A production-ready system for autonomous agent execution with sandboxed code execution, execution tracing, and comprehensive reporting. Agents plan complex tasks, execute code in isolated Docker containers, and generate artifacts—all with complete visibility into every step.

## Overview

This platform provides a complete infrastructure for running autonomous AI agents with a focus on safety, observability, and reproducibility. It combines:

- **Planning**: Multi-step task planning with dependency tracking
- **Execution**: Tool-based agent reasoning with support for multiple LLM providers
- **Sandboxing**: Isolated Docker-based execution environment for generated code
- **Evaluation**: Automated critique and revision loops for quality assurance
- **Visualization**: Real-time trace UI for monitoring and debugging
- **Reporting**: Structured reports from execution traces with schema validation

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
   └───────────────────────┘
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
│       ├── app/                # App router (Next.js 13+)
│       ├── components/         # React components
│       ├── lib/                # Utilities, API client
│       └── Dockerfile          # Trace UI container build
│
├── packages/                   # Shared Python libraries
│   ├── agent_core/             # Core agent reasoning
│   │   ├── planner.py
│   │   ├── executor.py
│   │   ├── llm.py
│   │   └── critic.py
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
├── content/docs/               # Documentation
│   └── getting-started.md      # Complete setup walkthrough
│
├── scripts/                    # Utility scripts
├── data/                       # Runtime data (artifacts, volumes)
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
- [API Documentation](docs/api.md) — Endpoint specifications
- [Architecture Deep Dive](docs/architecture.md) — System design details
- [Tool Development Guide](docs/tools.md) — Creating custom agent tools



**Built for autonomous execution with safety, observability, and precision.**
