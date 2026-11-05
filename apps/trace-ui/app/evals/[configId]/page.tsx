import { Suspense } from "react";
import Link from "next/link";
import {
  categoryLabel,
  configLine,
  fmtCost,
  fmtLatency,
  fmtPercent,
  getEvalReport,
  listEvalReports,
  listEvalRunIds,
  type EvalTaskResult,
} from "@/lib/evals";

const CATEGORY_ORDER = [
  "data_analysis",
  "multi_hop_research",
  "code_execution",
];

function statusTone(status: string): string {
  if (status === "PASS") return "chip--ok";
  if (status === "FAIL") return "chip--bad";
  return "chip--amber";
}

function rateTone(rate: number): string {
  if (rate >= 0.8) return "chip--ok";
  if (rate > 0) return "chip--amber";
  return "chip--bad";
}

function checkCount(result: EvalTaskResult): number {
  return result.details.filter((check) => check.passed).length;
}

async function EvalDetailContent({
  params,
}: {
  params: Promise<{ configId: string }>;
}) {
  const { configId } = await params;
  const report = getEvalReport(configId);

  if (!report) {
    return (
      <div className="empty">
        <h1 className="empty__title">Evaluation not found</h1>
        <p className="empty__line">
          Run <span className="empty__path">{configId}</span>
        </p>
        <div className="empty__actions">
          <Link href="/evals" className="btn btn--quiet">
            Back to evals
          </Link>
        </div>
      </div>
    );
  }

  const reports = listEvalReports();
  const latest = reports[0];
  const previous = reports[1];
  const compareTarget =
    latest && latest.run_id !== report.run_id
      ? latest
      : previous && previous.run_id !== report.run_id
        ? previous
        : null;

  const categories = Object.entries(report.summary.by_category).sort(
    ([a], [b]) => {
      const indexA = CATEGORY_ORDER.indexOf(a);
      const indexB = CATEGORY_ORDER.indexOf(b);
      return (
        (indexA === -1 ? CATEGORY_ORDER.length : indexA) -
        (indexB === -1 ? CATEGORY_ORDER.length : indexB)
      );
    }
  );

  return (
    <>
      <div className="page-head">
        <div>
          <Link href="/evals" className="link link--quiet">
            All evaluations
          </Link>
          <h1 className="page-head__title" style={{ marginTop: "var(--space-xs)" }}>
            {report.run_id}
          </h1>
          <p className="page-head__line">{configLine(report.config)}</p>
          <div className="meta" style={{ marginTop: "var(--space-sm)" }}>
            <div className="meta__item">
              <span className="meta__label">Config hash</span>
              <span className="meta__value mono">{report.config_hash}</span>
            </div>
            <div className="meta__item">
              <span className="meta__label">Dataset</span>
              <span className="meta__value">{report.dataset}</span>
            </div>
            <div className="meta__item">
              <span className="meta__label">Recorded</span>
              <span className="meta__value">
                {new Date(report.timestamp).toLocaleString()}
              </span>
            </div>
            <div className="meta__item">
              <span className="meta__label">Duration</span>
              <span className="meta__value mono">
                {report.duration_seconds.toFixed(2)}s
              </span>
            </div>
          </div>
        </div>
        <div className="page-head__actions">
          {compareTarget ? (
            <Link
              href={`/evals/compare/${report.run_id}/${compareTarget.run_id}`}
              className="btn btn--primary"
            >
              {compareTarget.run_id === latest?.run_id
                ? "Compare with latest"
                : "Compare with previous"}
            </Link>
          ) : null}
          <Link href="/evals" className="btn btn--quiet">
            Back to evals
          </Link>
        </div>
      </div>

      <div className="metrics metrics--five">
        <div className="metric">
          <span className="metric__value">
            {fmtPercent(report.summary.pass_rate)}
          </span>
          <span className="metric__label">
            Pass rate, {report.summary.passed} of {report.summary.total_tasks}
          </span>
        </div>
        <div className="metric">
          <span className="metric__value">
            {report.summary.passed}/{report.summary.total_tasks}
          </span>
          <span className="metric__label">
            Passed, {report.summary.failed} failed, {report.summary.errors} errors
          </span>
        </div>
        <div className="metric">
          <span className="metric__value">
            {fmtCost(report.summary.total_cost_usd)}
          </span>
          <span className="metric__label">Total cost</span>
        </div>
        <div className="metric">
          <span className="metric__value">
            {fmtLatency(report.summary.avg_latency_ms)}
          </span>
          <span className="metric__label">Average task latency</span>
        </div>
        <div className="metric">
          <span className="metric__value">
            {report.duration_seconds.toFixed(2)}s
          </span>
          <span className="metric__label">Wall-clock duration</span>
        </div>
      </div>

      <section className="final-output">
        <div className="timeline-head">
          <h2>By category</h2>
          <span className="panel__meta">
            {categories.length}{" "}
            {categories.length === 1 ? "category" : "categories"}
          </span>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th className="num-right">Passed</th>
                <th className="num-right">Failed</th>
                <th className="num-right">Errors</th>
                <th className="num-right">Avg score</th>
                <th className="eval-bar-col">Distribution</th>
              </tr>
            </thead>
            <tbody>
              {categories.map(([category, stats]) => (
                <tr key={category}>
                  <td>
                    <span className="table__task">{categoryLabel(category)}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{stats.passed}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{stats.failed}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{stats.errors}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{stats.avg_score.toFixed(2)}</span>
                  </td>
                  <td className="eval-bar-col">
                    <div className="meter" aria-hidden="true">
                      <div
                        className="meter__fill"
                        style={{
                          width: `${Math.max(2, stats.avg_score * 100)}%`,
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="final-output">
        <div className="timeline-head">
          <h2>Task results</h2>
          <span className="panel__meta">
            schema gate + 80% check threshold
          </span>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Category</th>
                <th>Result</th>
                <th className="num-right">Score</th>
                <th className="hide-sm num-right">Cost</th>
                <th className="hide-sm num-right">Latency</th>
                <th>Checks</th>
              </tr>
            </thead>
            <tbody>
              {report.results.map((result) => (
                <tr key={result.task_id}>
                  <td>
                    <span className="table__id">{result.task_id}</span>
                    <span className="table__task">{result.task}</span>
                    {result.error ? (
                      <span className="eval-error">{result.error}</span>
                    ) : null}
                  </td>
                  <td>
                    <span className="table__id">
                      {categoryLabel(result.category)}
                    </span>
                  </td>
                  <td>
                    <span className={`chip ${statusTone(result.status)}`}>
                      {result.status}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{result.score.toFixed(2)}</span>
                  </td>
                  <td className="hide-sm num-right">
                    <span className="table__num">{fmtCost(result.cost_usd)}</span>
                  </td>
                  <td className="hide-sm num-right">
                    <span className="table__num">
                      {fmtLatency(result.latency_ms)}
                    </span>
                  </td>
                  <td>
                    <details className="eval-checks">
                      <summary>
                        {checkCount(result)}/{result.details.length} passed
                      </summary>
                      <ul className="eval-checks__list">
                        {result.details.map((check, index) => (
                          <li
                            className={`eval-checks__item ${
                              check.passed
                                ? "eval-checks__item--ok"
                                : "eval-checks__item--bad"
                            }`}
                            key={`${check.scorer}-${index}`}
                          >
                            <span className="eval-checks__scorer">
                              {check.scorer}
                            </span>
                            <span className="eval-checks__score">
                              {check.score.toFixed(2)}
                            </span>
                            <span className="eval-checks__detail">
                              {check.details}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </details>
                    {result.output ? (
                      <details className="eval-checks">
                        <summary>output</summary>
                        <pre className="eval-output">{result.output}</pre>
                      </details>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="empty__line" style={{ marginTop: "var(--space-sm)" }}>
          Pass rate is{" "}
          <span className={`chip ${rateTone(report.summary.pass_rate)}`}>
            {fmtPercent(report.summary.pass_rate)}
          </span>{" "}
          for this config. Expand a row to inspect every scorer result and the
          raw task output.
        </p>
      </section>
    </>
  );
}

export function generateStaticParams() {
  return listEvalRunIds().map((configId) => ({ configId }));
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
