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
    <div className="shell page">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Evaluation results</h1>
          <p className="page-head__line">
            Committed eval reports show aggregate pass rates, per-task scores, regressions, and cost/latency analysis.
          </p>
          <p className="page-head__meta">
            {evals.length} {evals.length === 1 ? "committed report" : "committed reports"}
          </p>
        </div>
      </div>

      {evals.length === 0 ? (
        <div className="empty">
          <h2 className="empty__title">No evaluation reports yet</h2>
          <p className="empty__line">Committed eval reports appear here once an evaluation run finishes.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Report</th>
                <th className="num-right">Pass rate</th>
                <th className="num-right">Recorded</th>
              </tr>
            </thead>
            <tbody>
              {evals.map((eval_) => (
                <tr key={eval_.name}>
                  <td>
                    <Link href={`/evals/${eval_.name}`} className="table__task">
                      {eval_.name}
                    </Link>
                  </td>
                  <td className="num-right">
                    {eval_.passRate !== undefined ? (
                      <span className="table__num">{eval_.passRate}%</span>
                    ) : (
                      <span className="table__id">n/a</span>
                    )}
                  </td>
                  <td className="num-right">
                    <span className="table__num">{new Date(eval_.timestamp).toLocaleDateString()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
