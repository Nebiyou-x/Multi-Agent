import { readFileSync, readdirSync } from "fs";
import { join } from "path";
import Link from "next/link";

interface EvalResult {
  task: string;
  passed: boolean;
  score?: number;
  cost_usd?: number;
  latency_ms?: number;
  scorer?: string;
  detail?: string;
}

interface EvalReport {
  timestamp: string;
  config_hash: string;
  model: string;
  dataset: string;
  results: EvalResult[];
  aggregate?: {
    pass_rate: number;
    avg_cost: number;
    avg_latency: number;
    p50_latency: number;
    p95_latency: number;
  };
}

function loadEval(configId: string): EvalReport | null {
  try {
    const evalsDir = join(process.cwd(), "reports", "evals");
    const file = join(evalsDir, `${configId}.json`);
    const content = readFileSync(file, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function listCharts(): string[] {
  try {
    const chartsDir = join(process.cwd(), "reports", "evals", "charts");
    return readdirSync(chartsDir).filter((f) => f.endsWith(".png"));
  } catch {
    return [];
  }
}

export default function EvalDetailPage({ params }: { params: { configId: string } }) {
  const evalData = loadEval(params.configId);

  if (!evalData) {
    return (
      <div className="mx-auto w-full max-w-7xl px-6 py-10">
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold mb-2">Evaluation not found</h1>
          <p className="text-neutral-400 mb-6">Config: {params.configId}</p>
          <Link href="/evals" className="text-indigo-400 hover:text-indigo-300">
            ← Back to evals
          </Link>
        </div>
      </div>
    );
  }

  const passedCount = evalData.results.filter((r) => r.passed).length;
  const passRate = (passedCount / evalData.results.length * 100).toFixed(1);

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-10">
      <Link href="/evals" className="mb-6 text-indigo-400 hover:text-indigo-300 text-sm">
        ← Back to evals
      </Link>

      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{params.configId}</h1>
        <div className="flex flex-wrap gap-4 text-sm text-neutral-400 font-mono">
          <span>Model: {evalData.model}</span>
          <span>Dataset: {evalData.dataset}</span>
          <span>{new Date(evalData.timestamp).toLocaleDateString()}</span>
        </div>
      </div>

      <div className="grid gap-4 grid-cols-2 sm:grid-cols-5 mb-8">
        <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
          <div className="text-xs text-neutral-500 mb-1">Pass rate</div>
          <div className="font-mono text-2xl text-green-400 font-bold">{passRate}%</div>
          <div className="text-xs text-neutral-500 mt-1">{passedCount}/{evalData.results.length}</div>
        </div>
        {evalData.aggregate && (
          <>
            <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
              <div className="text-xs text-neutral-500 mb-1">Avg cost</div>
              <div className="font-mono text-lg">${evalData.aggregate.avg_cost.toFixed(4)}</div>
            </div>
            <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
              <div className="text-xs text-neutral-500 mb-1">Avg latency</div>
              <div className="font-mono text-lg">{(evalData.aggregate.avg_latency / 1000).toFixed(2)}s</div>
            </div>
            <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
              <div className="text-xs text-neutral-500 mb-1">P50 latency</div>
              <div className="font-mono text-lg">{(evalData.aggregate.p50_latency / 1000).toFixed(2)}s</div>
            </div>
            <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
              <div className="text-xs text-neutral-500 mb-1">P95 latency</div>
              <div className="font-mono text-lg">{(evalData.aggregate.p95_latency / 1000).toFixed(2)}s</div>
            </div>
          </>
        )}
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-bold mb-4">Results by task</h2>
        <div className="overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-950/40">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-[11px] uppercase tracking-wider text-neutral-600">
                <th className="px-4 py-3">Task</th>
                <th className="px-4 py-3">Scorer</th>
                <th className="px-4 py-3">Result</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Latency</th>
              </tr>
            </thead>
            <tbody>
              {evalData.results.map((result, idx) => (
                <tr key={idx} className="border-b border-neutral-800/50 hover:bg-neutral-900/30 transition-colors">
                  <td className="px-4 py-3 text-neutral-300">{result.task}</td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-500">{result.scorer || "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                        result.passed
                          ? "bg-green-600/20 text-green-300"
                          : "bg-red-600/20 text-red-300"
                      }`}
                    >
                      {result.passed ? "PASS" : "FAIL"}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{result.score?.toFixed(2) || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                    {result.cost_usd ? `$${result.cost_usd.toFixed(4)}` : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                    {result.latency_ms ? `${(result.latency_ms / 1000).toFixed(2)}s` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
