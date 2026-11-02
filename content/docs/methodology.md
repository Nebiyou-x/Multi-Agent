---
title: Evaluation Methodology
summary: How the eval harness scores a configuration, what counts as a regression, and how to read the charts.
order: 7
---

# Evaluation Methodology

How the eval harness measures a model + prompt + tooling configuration
against a golden dataset, and how to read the numbers it produces.

## Golden datasets

Golden tasks live under `datasets/golden/`. Each task defines a prompt,
the expected outcome, and which scorer checks it. Be honest about the
state of the set: it is small and still growing. `packages/eval/` is a
scaffold and `datasets/golden/` has no committed tasks yet, so there are
no published pass rates to cite - any number in a report today is only
as strong as the tasks behind it. The dataset version is recorded on
every eval report (`dataset_version`) precisely so that a pass rate
computed on 8 tasks is never silently compared against one computed on
40.

## Deterministic scorers vs LLM-as-judge

The scorer a task uses is first-class: every result in
`packages/report/schema.py` names one of `schema`, `numeric_tolerance`,
`code_test_pass_rate`, or `llm_judge`. The split is a deliberate one
(ADR-004):

- **Deterministic first.** Schema validation, numeric tolerance, and
  code-test pass rate cover the deterministic bulk of tasks. They are
  free, fast, and repeatable: the same report file always means the same
  thing, which is what CI needs.
- **LLM judges only where they earn their keep.** A judge is worth the
  noise and the per-task cost when the success criterion is genuinely
  open-ended (a chart is clear, a summary is faithful). Adding judges to
  tasks a deterministic check already settles just adds variance to a
  number that did not need it.

Practical consequence: when comparing two configurations, look at the
deterministic subset first. Judge-scored deltas can be within noise;
deterministic deltas cannot.

## Reading an eval report

An `EvalReport` (rendered by `packages/report`, `python -m report eval
results.json [--baseline baseline.json]`) presents four layers.
Aggregates are always recomputed on load, never trusted from the file.

1. **Aggregate table.** One row: `config_id`/`config_hash`, `provider`,
   `model`, `prompt_version`, `dataset_version`, task count, pass count
   and pass rate, average cost per task, p50/p95 latency. This is the
   number you quote. It is only meaningful with its `dataset_version`
   next to it.
2. **Per-task table.** One row per task: `task`, `scorer`, `result`
   (PASS/FAIL), `score` (0..1), `cost_usd`, `latency_ms`, and `detail`
   (the scorer's one-line explanation of why). This is where you go when
   the aggregate moved: which task, which scorer, which detail string.
3. **Delta vs baseline.** For a report run with a baseline, the diff is
   two lists: `regression(baseline)` - tasks that PASS at baseline but
   FAIL now - and `improvement(baseline)` - tasks that FAIL at baseline
   but PASS now. The delta line on the aggregate table is
   `pass_rate - baseline.pass_rate`; the callout box lists the regressed
   task names. A cost or latency delta without a pass-rate delta is
   noise until proven otherwise.
4. **Regression callout.** The red-boxed section at the top of the
   report. It is empty by design on a clean run; when it is not, it
   names the regressed tasks, their baseline result, their current
   result, and their scorer, so the fix is findable without re-running
   the suite.

## What counts as a regression

Definition, from `EvalReport.regression` in
`packages/report/schema.py`: **a task that PASSed at baseline but FAILs
in the current report.** That is it - not "score dropped", not "cost
went up". A task that failed both times is not a regression (it is a
known weakness to fix, tracked separately by the improvement list). The
mirror image, `improvement`, is a task that FAILed at baseline and PASSes
now. Both are computed against the baseline's task set; a task present
only in the current report cannot regress because it has no baseline.
The CLI refuses a baseline with the same `config_id` as the report, so a
regression is always a real cross-config comparison.

## What the charts mean

`report eval` writes three PNG charts under `charts/<config_id>/`,
rendered with matplotlib's Agg backend. They are byte-deterministic:
fixed figure size, sorted axes, no random state - the same input always
produces the same PNG bytes, so a chart diff in a PR means the numbers
changed.

- **Pass rate by config** (`pass_rate.png`). One bar per config; the
  baseline bar is gray, the report's bar green, value labeled. Read the
  `dataset_version` next to it: a jump that is *not* a config change is
  a dataset change, and the bars are only comparable when the versions
  match.
- **Cost per task** (`cost_per_task.png`). One bar per task, sorted by
  task name; green for PASS, red for FAIL. The x-axis is task name
  (truncated to 14 characters). When the config mixes deterministic and
  judge scorers, the mean blends two populations - use this chart plus
  the per-task table to see the split.
- **Latency distribution** (`latency_dist.png`). Histogram of per-task
  `latency_ms` with dashed p50 (red) and p95 (green) lines, nearest-rank
  percentiles. A p95 far above p50 means one or two tasks are slow
  (usually a critique loop hitting the revision cap); the per-task
  table tells you which.
