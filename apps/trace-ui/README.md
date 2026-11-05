# Trace UI

Next.js dashboard for reading committed traces, evaluation reports, and the
markdown docs in `content/docs/`.

## Views

| Route | Purpose |
| :---- | :------ |
| `/` | Workbench with the latest API run, recent runs, and docs |
| `/traces` | Committed trace reports from `reports/traces/` |
| `/traces/[runId]` | Step-by-step trace inspector |
| `/evals` | Bundled evaluation runs from `reports/evals/` |
| `/evals/[runId]` | Per-category summary, per-task scorer details, and raw task output |
| `/evals/compare/[a]/[b]` | Pass-rate, cost, latency, and PASS→FAIL regression comparison |
| `/docs` | Markdown documentation rendered from `content/docs/` |

Evaluation reports are bundled at build time by `lib/eval-data.ts`, which
imports the JSON files in `reports/evals/`. The pages never read the filesystem
at request time, so a static deployment shows the reports without a server.
After adding a new report, add its import to `lib/eval-data.ts` and rebuild.

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
