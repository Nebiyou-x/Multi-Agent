# Evaluation Framework: Agent Performance Tracking

A rigorous system for measuring and comparing agent performance across versions with deterministic scorers, golden datasets, and automated regression detection.

## Overview

The evaluation framework enables:
- **Golden Dataset**: 9 deterministic tasks across categories (data analysis, research, code execution)
- **Deterministic Scorers**: Schema validation, numeric tolerance, code test passes, citations, artifacts, and output length
- **Parallel Execution**: Run all tasks concurrently with configurable limits
- **Regression Detection**: Compare runs side-by-side, flag PASS→FAIL transitions
- **Cost & Latency Tracking**: Monitor per-task performance and aggregate metrics

The current pass path is fully deterministic. LLM-as-judge scoring is a planned extension, not part of the committed results.

## Architecture

```
Golden Dataset (tasks.jsonl)
         ↓
    [Task 1-9]
         ↓
    EvalRunner
    (parallel executor)
         ↓
  [Check Scorers] ← Schema, Numeric, CodeTest, Citations
         ↓
  TaskResult (score, status, details)
         ↓
  EvalRunReport (summary, per-task, by-category)
         ↓
  Regression Comparator
  (run1 vs run2 → regressions/improvements)
```

## Components

### Golden Dataset (`packages/eval/golden.py`)

The dataset consists of 9 default tasks across three categories, stored in JSONL format:

```json
{
  "task_id": "da_001",
  "task": "Fetch CSV from https://example.com/iris.csv, compute mean/median...",
  "category": "data_analysis",
  "expected_output_schema": {...},
  "checks": ["schema_valid", "numeric_tolerance"],
  "reference_answer": "{\"mean\": 5.843, \"median\": 5.8}",
  "created_at": "2026-11-05T..."
}
```

**Categories:**
- **data_analysis**: Fetch → compute → chart (3 tasks)
- **multi_hop_research**: Search → fetch → synthesize (3 tasks)
- **code_execution**: Generate code → test → validate (3 tasks)

### Scorers (`packages/eval/scorers.py`)

Deterministic checkers for each task output:

| Scorer | Purpose | Returns |
|--------|---------|---------|
| `schema_valid` | Validates JSON schema | Pass/Fail |
| `numeric_tolerance` | Numeric values within ±5% | 0.0-1.0 score |
| `exact_match` | Exact string/structure match | 0.0 or 1.0 |
| `code_passes_tests` | Checks test_results field | 0.0-1.0 score |
| `file_exists` | Artifact generation | 0.0-1.0 score |
| `citation_quality` | URLs/refs in output | 0.0-1.0 score |
| `output_length` | Minimum output size | 0.0-1.0 score |

**Scoring Logic:**
1. Always run `schema_valid` first
2. Run category-specific checks (from task definition); aliases such as `numeric_exact` and `source_count` resolve to canonical scorers
3. Aggregate: schema must pass and at least 80% of the remaining checks must pass
4. Overall score = mean of the schema score (0 or 1) and the check pass fraction

### Eval Runner (`packages/eval/runner.py`)

Executes evaluation runs with configuration tracking:

```python
runner = EvalRunner(max_parallel=4)
report = runner.run_eval(tasks, config)
runner.save_report(report)
```

**Report Structure:**
```python
EvalRunReport(
  run_id="eval_d3bd3327_20261105_105605",
  config_hash="d3bd3327",  # Hash of config for grouping
  config={"model": "gpt-4", "version": "1.0"},
  timestamp="2026-11-05T...",
  duration_seconds=1.33,
  results=[TaskResult(...)],  # Per-task results
  summary={
    "total_tasks": 9,
    "passed": 1,
    "failed": 8,
    "errors": 0,
    "pass_rate": 0.111,
    "avg_cost_usd": 0.005,
    "avg_latency_ms": 458,
    "by_category": {...}
  }
)
```

### Regression Comparator

Compare two evaluation runs:

```python
comparison = runner.compare_runs("eval_v1", "eval_v2")

# Result:
{
  "regressions": [
    {"task_id": "ce_001", "change": "PASS → FAIL", "score_delta": -0.83},
  ],
  "improvements": [
    {"task_id": "da_003", "change": "FAIL → PASS", "score_delta": +0.92},
  ],
  "summary": {
    "pass_rate_delta": -0.15,  # Negative = regression
    "cost_delta_usd": 0.0012,
    "latency_delta_ms": -45
  }
}
```

## CLI Usage

### Initialize Golden Dataset

```bash
make eval-init
# or
python scripts/eval.py init
```

Creates `datasets/golden/tasks.jsonl` with 9 default tasks.

### Run Evaluation

```bash
# With config
.venv/bin/python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown

# Default config (gpt-4, version 1.0)
.venv/bin/python scripts/eval.py run --markdown
```

Output:
```
Running 9 golden tasks...
  Config: {"model":"gpt-4","version":"1.0"}

✓ Evaluation complete in 1.33s
  Report: data/eval_results/eval_d3bd3327_20261105_105605.json
  Run ID: eval_d3bd3327_20261105_105605

Summary:
  Pass Rate: 11.1%
  Passed: 1/9
  Failed: 8
  Errors: 0
  Total Cost: $0.0450
  Avg Latency: 458ms

By Category:
  data_analysis: 1/3 passed
  multi_hop_research: 0/3 passed
  code_execution: 0/3 passed
```

### List All Runs

```bash
.venv/bin/python scripts/eval.py list

# Output:
Run ID                                        Pass Rate    Cost         Latency     
eval_4b4b83c1_20261105_105608                 11.1%        $0.0450      507ms
eval_d3bd3327_20261105_105605                 11.1%        $0.0450      675ms
```

### Compare Runs (Regression Detection)

```bash
.venv/bin/python scripts/eval.py compare \
  --run1 eval_d3bd3327_20261105_105605 \
  --run2 eval_4b4b83c1_20261105_105608 \
  --markdown

# Output:
Regression Report:
  Total Tasks: 9
  Regressions: 0
  Improvements: 0
  Pass Rate Delta: +0.0%
  Cost Delta: $+0.0000
  Latency Delta: -112ms
```

### Show Run Details

```bash
.venv/bin/python scripts/eval.py show eval_d3bd3327_20261105_105605
```

Outputs full markdown report with all task results.

## Workflow: compare a baseline and a variant

### Step 1: Establish the baseline

```bash
python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown
# → eval_d3bd3327_20261105_105605.json: 1/9 passed (11.1%), avg latency 675ms
```

### Step 2: Run the variant

```bash
python scripts/eval.py run --config '{"model":"claude-opus","version":"2.0"}' --markdown
# → eval_4b4b83c1_20261105_105608.json: 1/9 passed (11.1%), avg latency 507ms
```

### Step 3: Detect regressions

```bash
python scripts/eval.py compare \
  --run1 eval_d3bd3327_20261105_105605 \
  --run2 eval_4b4b83c1_20261105_105608 \
  --markdown
```

Output for these committed runs:

```
Regression Report:
  Total Tasks: 9
  Regressions: 0
  Improvements: 0
  Pass Rate Delta: +0.0%
  Cost Delta: $+0.0000
  Latency Delta: -167ms
```

The report exits non-zero only when a PASS→FAIL transition is detected. The Trace UI renders the same comparison at `/evals/compare/{run_a}/{run_b}`.

> **Why these runs tie:** the committed results come from the deterministic mock executor in `runner.run_task()`. Identical pass rates prove the dataset, scorer, report, and comparison pipeline agree; they do not measure model quality. Replace the mock with `packages.agent_core.executor` to get model-specific deltas.

### Step 4: Root-cause analysis

```bash
# Full report for either run
python scripts/eval.py show eval_d3bd3327_20261105_105605
python scripts/eval.py show eval_4b4b83c1_20261105_105608

# In the Trace UI, expand a task row to inspect every scorer and its output
```

## Adding Custom Tasks

```python
from packages.eval.golden import GoldenDataset, GoldenTask

dataset = GoldenDataset()
dataset.save_task(GoldenTask(
    task_id="custom_001",
    task="Your task description",
    category="data_analysis",
    expected_output_schema={
        "type": "object",
        "properties": {...},
        "required": [...]
    },
    checks=["schema_valid", "numeric_tolerance"],
    reference_answer='{"result": 42}'
))
```

## Adding Custom Scorers

```python
from packages.eval.scorers import DeterministicScorer, scorer_registry

class CustomScorer(DeterministicScorer):
    def score(self, output, reference, task_id="", **kwargs):
        # Your scoring logic
        passed = ...
        score = ...
        return ScorerResult(task_id, "custom_name", passed, score, "details")

scorer_registry.register("custom_name", CustomScorer().score)
```

Then add "custom_name" to task checks:
```python
checks=["schema_valid", "custom_name"]
```

## Files & Locations

```
datasets/golden/
  └── tasks.jsonl           # Golden tasks (JSONL format)

data/eval_results/
  ├── eval_*.json           # Run reports (JSON)
  ├── eval_*.md             # Run reports (Markdown)
  └── comparison_*.md       # Regression reports

packages/eval/
  ├── golden.py             # Task dataset loader
  ├── scorers.py            # Deterministic scorers
  ├── runner.py             # Eval executor & reporter
  └── __init__.py

scripts/
  └── eval.py               # CLI interface
```

## Performance Expectations

With current mock executor:
- **9 tasks**: ~1.3 seconds total
- **Per-task**: 100-520ms (includes mock sleep)
- **Cost**: $0.045 (mock pricing)
- **Run reports**: < 10 seconds for parallel execution
- **Regression comparison**: < 1 second

For real agent execution:
- **Per-task latency**: Depends on agent model + tool calls (typically 2-30s)
- **Total cost**: Model-dependent (e.g., $0.10-0.50 for 9 tasks)
- **Recommendation**: Batch runs by config to amortize setup

## Integration with CI/CD

```yaml
# Example GitHub Actions
- name: Eval Baseline
  run: python scripts/eval.py run --config '{"model":"gpt-4"}' --markdown

- name: Compare vs Baseline
  run: python scripts/eval.py compare --run1 BASELINE_ID --run2 HEAD_ID --markdown

- name: Fail if regressions
  run: |
    if [ $? -ne 0 ]; then
      echo "⚠️  Regressions detected"
      exit 1
    fi
```

## Roadmap

- [ ] LLM-as-judge scorer with cached prompts
- [ ] Multi-agent comparison (e.g., Claude vs GPT vs Gemini)
- [ ] Historical trend tracking (regression over N versions)
- [ ] Cost vs accuracy Pareto frontier
- [ ] Interactive dashboard for run exploration
