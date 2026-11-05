# Trace UI

Next.js dashboard for reading committed traces, evaluation reports, and the
markdown docs in `content/docs/`.

## Views

| Route | Purpose |
| :---- | :------ |
| `/` | Workbench with the latest API run, recent runs, and docs |
| `/traces` | Committed trace reports from `reports/traces/` |
| `/traces/[runId]` | Step-by-step trace inspector |
| `/evals` | Committed evaluation runs from `reports/evals/` and `data/eval_results/` |
| `/evals/[runId]` | Per-category summary, per-task scorer details, and raw task output |
| `/evals/compare/[a]/[b]` | Pass-rate, cost, latency, and PASS→FAIL regression comparison |
| `/docs` | Markdown documentation rendered from `content/docs/` |

Evaluation reports are loaded server-side by `lib/evals.ts`. The loader accepts
the JSON reports written by `packages/eval/runner.py` and normalizes older
sample reports when needed. `EVALS_DIR` can override the report directory.

## Development

```bash
npm install
npm run dev     # http://localhost:3000
npm run lint
npm run build
```

The run workbench reads the agent API from `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`). Evaluation and trace views are file-backed and do not
need the API.
