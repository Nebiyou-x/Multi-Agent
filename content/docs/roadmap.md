---
title: Roadmap
summary: What lands next, plus the honest list of known limitations.
order: 8
---

# Roadmap

What comes next, and what we are knowingly not doing yet. The "next"
list is ordered roughly by dependency, not by difficulty.

## Next steps

### Multi-tool orchestration

Today the planner builds one DAG and the executor walks it topologically,
one subtask at a time. The near-term work is letting independent
subtasks run in parallel (safe: tools are stateless per call and
artifacts are per-run), and letting one `code_execution` step call back
into other tools through its own data rather than re-planning the whole
task. The dependency protocol already supports this - `depends_on` plus
`/in` mounting is the wiring; what is missing is the concurrent
scheduler and the prompt guidance for when to fan out.

### LLM-judge scorers

`llm_judge` is already a first-class scorer name in the frozen schema
(`packages/report/schema.py`) but has no implementation. Plan per ADR-004:
wire it only for the open-ended tasks, use two judges with a
majority/cascade rule to dampen noise, record the judge model and prompt
version on the task so a judge upgrade is a visible dataset change, and
report judge-scored results separately from deterministic ones.

### OpenTelemetry export

ADR-001 keeps the custom trace schema as the source of truth and treats
OTel as an optional side channel. The next piece is an exporter that
walks a `TraceRun`, emits spans for the service hops (API call, LLM
call, sandbox exec, Postgres write) with the semantic step data as
attributes, and pushes to whatever collector the host has. It runs
after persistence, so a broken collector never blocks a run.

### More golden tasks

The highest-leverage item. `datasets/golden/` is nearly empty; every
other eval feature is capped by dataset size. Plan: add tasks across the
four tools (fetch + chart, search + synthesize, SQL + aggregate,
multi-step with artifacts), prefer deterministic scorers, tag each with
a `dataset_version` bump, and keep a known-bad task in the set on
purpose so the pipeline is caught when it breaks.

### CI report generation

Close the loop on ADR-005: a CI job that (1) runs the eval suite
against the golden set, (2) renders Markdown + HTML reports into
`reports/`, and (3) fails the build on any regression vs the committed
baseline (PASS at baseline, FAIL now). The Next.js UI gets a static
lens over `reports/` so reviewers can open a report artifact without a
live Postgres. This lands after the golden set is big enough to make
the gate meaningful.

## Known limitations (honest list)

- **Single Postgres trace store.** Traces live in one Postgres database
  (compose volume `pgdata`). No sharding, no retention policy, no
  read replicas; a lost volume loses history. Adequate for a solo dev
  box, not for production traffic.
- **No authentication on the API.** `POST /runs` will execute LLM calls
  and spend real tokens from anyone who can reach port 8000. This is a
  localhost tool; exposing it requires adding auth before anything
  else.
- **Single-container, single-tenant sandbox.** The Docker sandbox
  contains one execution at a time with per-container caps
  (`docs/sandbox.md` non-goals). There is no per-tenant isolation, no
  pool of warm containers, and a Docker-daemon failure takes code
  execution down with it.
- **Small eval dataset.** Pass rates today carry wide confidence
  intervals by construction. Treat every number as provisional until
  the golden set grows; that is why `dataset_version` is on every
  report.
- **Replay cost is unbounded per user choice.** Two replays of a task
  on a large model cost real money; there is no per-run budget cap in
  the API. The LLM retry/backoff in `packages/agent_core/llm.py`
  bounds transport retries, not spend.
- **Report generator dependencies are undeclared.** `packages/report`
  imports `jinja2` and `matplotlib`, which are present in the local
  `.venv` but not in `requirements-dev.txt` or the API image's
  `requirements.txt`; the eval subcommand will not work in a clean
  install until those are declared.
- **Known syntax bug in the report schema.** `packages/report/schema.py`
  uses `in` as a Pydantic field name (`in: int` inside `TokenUsage`),
  which is a keyword and does not parse under Python 3.12 - `python -m
  report` currently fails at import. The CLI and renderers are written
  and tested against the module; the docs citing `python -m report` are
  accurate for the fixed state.
