# Agent Evaluation System — Quick Start

## 5-Minute Setup

```bash
# 1. Initialize golden dataset (one time)
make eval-init

# 2. Run baseline evaluation
python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown

# 3. Run variant for comparison
python scripts/eval.py run --config '{"model":"claude-opus","version":"2.0"}' --markdown

# 4. Compare runs and detect regressions
python scripts/eval.py list  # Get run IDs
python scripts/eval.py compare --run1 <run1_id> --run2 <run2_id> --markdown
```

## Golden Dataset

9 default tasks stored in `datasets/golden/tasks.jsonl`:

| Category | Task IDs | Purpose |
|----------|----------|---------|
| **Data Analysis** | da_001, da_002, da_003 | Fetch → compute → chart |
| **Multi-Hop Research** | mhr_001, mhr_002, mhr_003 | Search → fetch → synthesize |
| **Code Execution** | ce_001, ce_002, ce_003 | Generate code → test → validate |

Each task specifies:
- Task description
- Expected output schema (JSON Schema)
- Checks to run (schema_valid, numeric_tolerance, etc.)
- Reference answer (for ground truth comparison)

## Scorers

Deterministic validation of outputs:

- **schema_valid** — Output conforms to task schema (required)
- **numeric_tolerance** — Numbers within ±5% of reference
- **exact_match** — String/structure matches exactly
- **code_passes_tests** — test_results.passed ≥ 80%
- **file_exists** — Expected artifacts were generated
- **citation_quality** — URLs or citation markers present
- **output_length** — Minimum length requirement met

**Scoring:** Schema must pass, and at least 80% of the remaining checks must pass, for a task to count as PASS. The task score is the mean of the schema score and the check pass fraction.

## Reports

Each run produces:

```
data/eval_results/
  ├── eval_HASH_TIMESTAMP.json    # Full results (JSON)
  └── eval_HASH_TIMESTAMP.md      # Summary (Markdown)
```

**Report Contents:**
- Per-task: status, score, check details
- By-category: pass rate, avg score
- Aggregate: pass rate, cost, latency

## Regression Detection

Compare two runs to identify regressions:

```bash
python scripts/eval.py compare --run1 v1_id --run2 v2_id --markdown
```

**Output:**
- Regressions: PASS → FAIL transitions (flagged with ⚠️ )
- Improvements: FAIL → PASS transitions (flagged with ✅)
- Metrics: pass rate delta, cost delta, latency delta

Exit code = 1 if regressions found (CI/CD integration ready)

## Example: compare the committed baseline and variant

```bash
# Baseline
$ python scripts/eval.py run --config '{"model":"gpt-4","version":"1.0"}' --markdown
# eval_d3bd3327_20261105_105605.json: 11.1% pass rate (1/9)

# Variant
$ python scripts/eval.py run --config '{"model":"claude-opus","version":"2.0"}' --markdown
# eval_4b4b83c1_20261105_105608.json: 11.1% pass rate (1/9)

# Compare
$ python scripts/eval.py compare \
    --run1 eval_d3bd3327_20261105_105605 \
    --run2 eval_4b4b83c1_20261105_105608 \
    --markdown

# Output:
# Pass Rate Delta: +0.0%
# Regressions: 0
# Improvements: 0
# Latency Delta: -167ms
```

These reports were produced by the mock executor in `runner.run_task()`, so the
scoring pipeline is exercised end to end but model quality is not measured.
After wiring the live agent executor, the same commands surface PASS→FAIL
regressions and FAIL→PASS improvements for real model changes. The Trace UI
shows the same comparison at `/evals/compare/{run_a}/{run_b}`.

## Example: what a regression report looks like once connected

```text
# Pass Rate Delta: +15.0%
# Regressions: 2
#   - ce_001: PASS → FAIL (-0.83)
#   - da_003: PASS → FAIL (-0.92)
# Improvements: 4
#   - mhr_001: FAIL → PASS (+0.78)
#   - mhr_003: FAIL → PASS (+0.85)
```

## CLI Commands

```
eval init              # Create golden dataset
eval run               # Run evaluation (use --markdown to export)
eval list              # Show all runs
eval show <run_id>     # View run details
eval compare           # Compare two runs (detect regressions)

Options:
  --config JSON        # Config dict (e.g., '{"model":"gpt-4"}')
  --run1, --run2       # Run IDs to compare
  --markdown           # Export markdown reports
  --max-parallel N     # Parallel tasks (default: 4)
```

## Adding Tasks

```python
from packages.eval.golden import GoldenDataset, GoldenTask

dataset = GoldenDataset()
dataset.save_task(GoldenTask(
    task_id="custom_001",
    task="Your task",
    category="data_analysis",
    expected_output_schema={
        "type": "object",
        "properties": {
            "result": {"type": "number"},
            "chart": {"type": "string"}
        },
        "required": ["result", "chart"]
    },
    checks=["schema_valid", "numeric_tolerance", "file_exists"],
    reference_answer='{"result": 42}'
))
```

## Integration Points

### Modify to Use Real Agent

In `packages/eval/runner.py`, the `run_task` method currently mocks execution:

```python
async def run_task(self, task, task_index, semaphore):
    # Replace this:
    output = {"status": "success", "result": "mock"}
    
    # With real agent execution:
    from packages.agent_core.executor import execute_step
    # ... call agent with task.task
```

### Add Custom Scorers

```python
from packages.eval.scorers import DeterministicScorer, scorer_registry

class MyScorer(DeterministicScorer):
    def score(self, output, reference, **kwargs):
        passed = ...
        score = ...
        return ScorerResult(..., passed, score, ...)

scorer_registry.register("my_check", MyScorer().score)
```

Then use in tasks: `checks=["schema_valid", "my_check"]`

### CI/CD Integration

```yaml
# .github/workflows/eval.yml
name: Agent Evaluation
on: [push, pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make eval-init
      - run: python scripts/eval.py run --markdown
      - name: Compare vs baseline
        run: |
          BASELINE=$(python scripts/eval.py list | head -2 | tail -1)
          HEAD=$(python scripts/eval.py list | head -1)
          python scripts/eval.py compare --run1 "$BASELINE" --run2 "$HEAD"
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: eval-reports
          path: data/eval_results/
```

## Key Metrics

- **Pass Rate** — Fraction of tasks passing (80% score threshold)
- **Cost** — Total API spend (model-specific, tracked per task)
- **Latency** — Avg time per task (setup + execution + scoring)
- **By-Category** — Pass rate and avg score per category

## Files

```
datasets/golden/tasks.jsonl           # Golden tasks
data/eval_results/eval_*.json         # Run reports
scripts/eval.py                       # CLI
packages/eval/
  ├── golden.py                       # Dataset loader
  ├── scorers.py                      # Scoring logic
  └── runner.py                       # Executor
```

## Next Steps

1. **Initialize**: `make eval-init`
2. **Run baseline**: `python scripts/eval.py run --markdown`
3. **Modify agent**: Edit `packages/agent_core/executor.py` or similar
4. **Run variant**: `python scripts/eval.py run --markdown --config '{"version":"2.0"}'`
5. **Compare**: `python scripts/eval.py compare --run1 <v1> --run2 <v2> --markdown`
6. **Analyze**: Check markdown reports for regressions and improvements

---

See [full documentation](./evaluation.md) for architecture details, custom scorers, and advanced usage.
