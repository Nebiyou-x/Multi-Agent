import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import Link from "next/link";

interface EvalFile {
  name: string;
  timestamp: string;
  passRate?: number;
}

function listEvals(): EvalFile[] {
  try {
    const evalsDir = join(process.cwd(), "reports", "evals");
    const files = readdirSync(evalsDir).filter((f) => f.endsWith(".json"));

    return files
      .map((file) => {
        try {
          const content = readFileSync(join(evalsDir, file), "utf-8");
          const data = JSON.parse(content);
          const passCount = data.results?.filter((r: any) => r.passed).length || 0;
          const totalCount = data.results?.length || 0;
          const passRate = totalCount > 0 ? (passCount / totalCount * 100).toFixed(1) : null;
          return {
            name: file.replace(".json", ""),
            timestamp: data.timestamp || new Date().toISOString(),
            passRate: passRate ? parseFloat(passRate) : undefined,
          };
        } catch {
          return null;
        }
      })
      .filter(Boolean) as EvalFile[];
  } catch {
    return [];
  }
}

export default function EvalsPage() {
  const evals = listEvals().sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Evaluation Results</h1>
        <p className="text-neutral-400">
          Committed eval reports show aggregate pass rates, per-task scores, regressions, and cost/latency analysis.
        </p>
      </div>

      {evals.length === 0 ? (
        <div className="rounded-lg border border-neutral-800 p-8 text-center">
          <p className="text-neutral-400">No evaluation reports yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {evals.map((eval_) => (
            <Link
              key={eval_.name}
              href={`/evals/${eval_.name}`}
              className="group p-6 rounded-lg border border-neutral-800 bg-neutral-950/40 hover:border-indigo-600/50 hover:bg-neutral-900/60 transition-all flex items-center justify-between"
            >
              <div>
                <h3 className="font-semibold text-lg group-hover:text-indigo-300 transition-colors mb-1">
                  {eval_.name}
                </h3>
                <div className="text-xs text-neutral-500">
                  {new Date(eval_.timestamp).toLocaleDateString()}
                </div>
              </div>
              {eval_.passRate !== undefined && (
                <div className="text-right">
                  <div className="font-mono text-xl font-bold text-green-400">{eval_.passRate}%</div>
                  <div className="text-xs text-neutral-500">pass rate</div>
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
