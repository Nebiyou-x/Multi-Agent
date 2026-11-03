import { Suspense } from "react";
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

async function EvalDetailContent({
  params,
}: {
  params: Promise<{ configId: string }>;
}) {
  const { configId } = await params;
  const evalData = loadEval(configId);

  if (!evalData) {
    return (
      <div className="empty">
        <h1 className="empty__title">Evaluation not found</h1>
        <p className="empty__line">
          Config <span className="empty__path">{configId}</span>
        </p>
        <div className="empty__actions">
          <Link href="/evals" className="btn btn--quiet">
            Back to evals
          </Link>
        </div>
      </div>
    );
  }

  const passedCount = evalData.results.filter((r) => r.passed).length;
  const passRate = ((passedCount / evalData.results.length) * 100).toFixed(1);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-head__title">{configId}</h1>
          <div className="meta">
            <div className="meta__item">
              <span className="meta__label">Model</span>
              <span className="meta__value">{evalData.model}</span>
            </div>
            <div className="meta__item">
              <span className="meta__label">Dataset</span>
              <span className="meta__value">{evalData.dataset}</span>
            </div>
            <div className="meta__item">
              <span className="meta__label">Recorded</span>
              <span className="meta__value">
                {new Date(evalData.timestamp).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
        <div className="page-head__actions">
          <Link href="/evals" className="btn btn--quiet">
            Back to evals
          </Link>
        </div>
      </div>

      <div
        className={`metrics${
          evalData.aggregate ? " metrics--five" : " metrics--three"
        }`}
      >
        <div className="metric">
          <span className="metric__value">{passRate}%</span>
          <span className="metric__label">
            Pass rate, {passedCount} of {evalData.results.length}
          </span>
        </div>
        {evalData.aggregate && (
          <>
            <div className="metric">
              <span className="metric__value">
                ${evalData.aggregate.avg_cost.toFixed(4)}
              </span>
              <span className="metric__label">Average cost</span>
            </div>
            <div className="metric">
              <span className="metric__value">
                {(evalData.aggregate.avg_latency / 1000).toFixed(2)}s
              </span>
              <span className="metric__label">Average latency</span>
            </div>
            <div className="metric">
              <span className="metric__value">
                {(evalData.aggregate.p50_latency / 1000).toFixed(2)}s
              </span>
              <span className="metric__label">P50 latency</span>
            </div>
            <div className="metric">
              <span className="metric__value">
                {(evalData.aggregate.p95_latency / 1000).toFixed(2)}s
              </span>
              <span className="metric__label">P95 latency</span>
            </div>
          </>
        )}
      </div>

      <section className="final-output">
        <div className="timeline-head">
          <h2>Results by task</h2>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Scorer</th>
                <th>Result</th>
                <th className="num-right">Score</th>
                <th className="num-right">Cost</th>
                <th className="num-right">Latency</th>
              </tr>
            </thead>
            <tbody>
              {evalData.results.map((result, idx) => (
                <tr key={idx}>
                  <td>{result.task}</td>
                  <td>
                    <span className="table__id">{result.scorer || "n/a"}</span>
                  </td>
                  <td>
                    <span
                      className={`chip ${
                        result.passed ? "chip--ok" : "chip--bad"
                      }`}
                    >
                      {result.passed ? "Pass" : "Fail"}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">
                      {result.score?.toFixed(2) || "n/a"}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">
                      {result.cost_usd
                        ? `$${result.cost_usd.toFixed(4)}`
                        : "n/a"}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">
                      {result.latency_ms
                        ? `${(result.latency_ms / 1000).toFixed(2)}s`
                        : "n/a"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

export default function EvalDetailPage({
  params,
}: {
  params: Promise<{ configId: string }>;
}) {
  return (
    <div className="shell page">
      <Suspense fallback={<p className="empty__line">Loading evaluation…</p>}>
        <EvalDetailContent params={params} />
      </Suspense>
    </div>
  );
}