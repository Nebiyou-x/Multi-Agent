---
title: Design Decisions
summary: Five ADRs covering the trace schema, sandbox, bounded critic loop, scorers and static reports.
order: 6
---

# Design Decisions

Five ADRs that shape the system. Each has Context, Decision,
Consequences, and Alternatives considered; where a decision is
implemented today, the code location is noted.

---

## ADR-001: Custom trace schema vs OpenTelemetry spans

### Context

The trace recorder is the backbone: the critic routes retries off step
errors, the report generator renders the step tree, the eval harness
aggregates cost/latency. Whatever we record, we read back a lot. The
question was whether to model a run as OpenTelemetry spans or a custom
semantic schema.

### Decision

Custom semantic schema. Step types are `plan | tool_call | llm_call |
critique | revision | code_exec`; every step carries token and cost
attribution (`tokens {in, out}`, `cost_usd`, `latency_ms`) and a
`parent_step_id` edge so a run renders as a plan/revision tree. OTel
emission, if ever needed, is an optional side-channel - the custom
record stays the source of truth.

Rationale: OTel models infrastructure spans ("request hit a service,
took N ms, called a DB") and has no vocabulary for "the planner emitted
a 5-step DAG" or "this revision is nested under that critique". The
reasoning steps are the unit of analysis, and token/cost attribution
has to live on the step because that is where money is spent.
Implemented in `packages/trace/src/trace/schemas.py` (runtime) and
`packages/report/schema.py` (frozen contract; adds `code_exec` and
base64 `artifacts`).

### Consequences

- The step tree, verdicts, and per-step cost render directly - richer
  than an off-the-shelf dashboard.
- No OTel collector interop for free; sharing traces with
  infrastructure telemetry means writing an exporter.
- The schema is versioned (`schema_version: "1.0"`) and validated on
  load with loud failures, because the report pipeline trusts it.

### Alternatives considered

- **OpenTelemetry spans only.** Wrong abstraction for agent reasoning;
  token/cost per step does not fit a span attribute shape without
  abusing the model.
- **OTel plus custom span attributes.** Then the custom attributes
  *are* the schema we would have written anyway, with the dependency and
  collector in the hot path for no benefit at this scale.

---

## ADR-002: Docker sandbox vs WASM / gVisor

### Context

`code_execution` runs LLM-generated Python that does real data work
(pandas, numpy, matplotlib) under isolation. The options were Docker
with hardening flags, a WASM runtime, or gVisor.

### Decision

Docker: one ephemeral container per execution with `--network none`,
`--read-only` root, 512m memory, 0.5 CPU, a 64m `/tmp` tmpfs, read-only
bind mounts for script and inputs, a writable `/out`, and a wall-clock
timeout that kills and destroys the container.

Rationale: WASM lacks the Python data-science ecosystem and would force
a rewrite of the task vocabulary; gVisor adds operational complexity a
solo project cannot afford. The threat model is LLM-generated code on a
trusted host, not hostile tenants - Docker's flags already contain it,
cheaply.

### Consequences

- Works on any host with a Docker daemon; the API just mounts the
  socket.
- Isolation is per-container, not per-tenant; no guarantee against a
  determined host-level attacker (see `docs/sandbox.md` non-goals).
- A broken Docker daemon breaks code execution - surfaced as a
  `warnings` entry on the run.

### Alternatives considered

- **WASM (e.g. Pyodide).** No pandas/matplotlib story; too small a
  runtime for the tasks we run.
- **gVisor.** Stronger kernel isolation than needed for the threat model,
  at an ops cost a solo project cannot carry.
- **Run code in the API container directly.** No. An LLM-generated
  infinite loop or `rm -rf` would take down the service.

---

## ADR-003: Bounded critic loop

### Context

The critic REVISEs the final answer on missing data, hallucination, or
wrong format. An unbounded self-critique loop either oscillates (each
revision reintroduces the fault the critique rejected) or converges to
nothing. Both burn tokens and cost for no quality gain.

### Decision

Bound the loop: at most `MAX_REVISIONS` iterations (env, default 3, in
`apps/api/main.py`). On the final iteration the outcome is forced to
PASS - the last revision is accepted - and the force-pass is logged as
a metric so a high force-pass rate reads as "the critic is not
succeeding, the loop is just running out". A REVISE mid-loop runs one
revision pass, nested under the critique step via `parent_step_id`.

Note the current implementation achieves the same effect by ending the
run `succeeded` when the loop is exhausted; the force-pass metric is
the piece to make explicit. Until it is, watch for runs ending
"succeeded" after three critiques.

### Consequences

- Bounded cost ceiling: plan + N steps + (critique + revision) x 3 worst
  case.
- A REVISE after the last allowed iteration is swallowed silently in the
  trace unless someone reads the cap - hence the force-pass metric.
- `MAX_REVISIONS` is a dial: raise it to spend more tokens on weak tasks.

### Alternatives considered

- **Unbounded loop until PASS.** Cost has no ceiling; oscillation
  observed on real runs makes this worse, not better.
- **Stop on "no improvement".** Needs a per-iteration quality score that
  the critic does not reliably produce; the cap is simpler and testable.

---

## ADR-004: Deterministic scorers before LLM-as-judge

### Context

The eval harness scores golden tasks. LLM judges are available
(`llm_judge` is a scorer name in `packages/report/schema.py`), but they
cost money per task, add latency, and are themselves noisy: the same
answer can score differently run to run. A solo project needs numbers
it can trust from one CI pass.

### Decision

Deterministic scorers first: schema validation (output matches the
expected JSON/Pydantic shape), numeric tolerance (answers within a
configured epsilon of the golden value), and code-test pass rate (do the
fixture's unit tests pass). These three cover ~70% of tasks, because
most have a checkable output. LLM judges are added only where the
success criterion is genuinely open-ended (a chart is "clear", a summary
is "faithful") and only there, where their noise is tolerable against
their signal.

### Consequences

- Eval runs are fast, cheap, and repeatable - the same report file
  always means the same thing.
- The ~30% of tasks needing judgment stay unmeasured until we add
  judges; pass rates undercount quality there.
- The scorer is a first-class field on every `EvalTask` result, so a
  mixed deterministic/judge dataset reports which number came from
  where.

### Alternatives considered

- **All-LLM judging.** Noisy, expensive per CI run; hides regressions
  the deterministic scorers catch for free.
- **No LLM judges at all.** Leaves open-ended tasks unscored; revisit
  as the golden set grows.

---

## ADR-005: Static committed reports over a live UI

### Context

The Next.js trace viewer (`apps/trace-ui`, port 3000) reads live from
`GET /runs` and Postgres - great for debugging *this* run, wrong tool
for answering "did the prompt change on main make model B worse than
model A?" Live data is transient, unversioned, and nobody reviews a
dashboard in a pull request.

### Decision

Generate reports as artifacts: Markdown + self-contained HTML, written
to `reports/`, committed to the repo, diffed in PRs. The generator
(`packages/report`: `report trace`, `report eval`, `report build-index`)
renders those artifacts; the Next.js app is a static lens over them -
it inspects runs, it does not own the record.

Rationale: reproducibility (the bytes a reviewer sees are the bytes in
git), CI-friendliness (a job that renders and fails on a regression is
trivial; one that "checks the dashboard" is not), and no stateful
service between a developer and the answer.

### Consequences

- Reports are as fresh as the last generated commit; the live UI remains
  for exploration.
- `reports/` growth is bounded - traces are small text and base64
  artifacts are capped (~1MB per run total).
- The frozen schema in `packages/report/schema.py` makes committed files
  verifiable: loaders fail loudly on a field mismatch.

### Alternatives considered

- **Live dashboard as the record.** Unversioned and environment-
  dependent; a deleted row takes the report with it.
- **Artifact store (S3 et al.).** More infra, same benefit as git
  files, worse review ergonomics.
