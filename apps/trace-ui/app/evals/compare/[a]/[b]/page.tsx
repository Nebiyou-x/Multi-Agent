import { Suspense } from "react";
import Link from "next/link";
import {
  categoryLabel,
  compareEvalReports,
  configLine,
  fmtCost,
  fmtLatency,
  fmtPercent,
  getEvalReport,
  type EvalTaskComparison,
} from "@/lib/evals";

function statusTone(status: string | undefined): string {
  if (status === "PASS") return "chip--ok";
  if (status === "FAIL") return "chip--bad";
  if (status === "ERROR") return "chip--amber";
  return "chip--muted";
}

function changeTone(row: EvalTaskComparison): string {
  if (row.regression) return "chip--bad";
  if (row.improvement) return "chip--ok";
  return "chip--muted";
}

function signedPoints(value: number): string {
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} pts`;
}

function signedCost(value: number): string {
  return `${value > 0 ? "+" : ""}$${value.toFixed(4)}`;
}

function signedLatency(value: number): string {
  return `${value > 0 ? "+" : ""}${Math.round(value)}ms`;
}

function deltaClass(value: number, goodWhenLower = false): string {
  if (Math.abs(value) < 0.0001) return "delta delta--same";
  const good = goodWhenLower ? value < 0 : value > 0;
  return `delta ${good ? "delta--ok" : "delta--bad"}`;
}

async function CompareContent({
  params,
}: {
  params: Promise<{ a: string; b: string }>;
}) {
  const { a, b } = await params;
  const runA = getEvalReport(a);
  const runB = getEvalReport(b);

  if (!runA || !runB) {
    return (
      <div className="empty">
        <h1 className="empty__title">Evaluation comparison not found</h1>
        <p className="empty__line">
          Could not load{" "}
          <span className="empty__path">{!runA ? a : b}</span>.
        </p>
        <div className="empty__actions">
          <Link href="/evals" className="btn btn--quiet">
            Back to evals
          </Link>
        </div>
      </div>
    );
  }

  const comparison = compareEvalReports(runA, runB);
  const unchanged = comparison.rows.filter(
    (row) => !row.regression && !row.improvement
  );

  const metrics: Array<{
    label: string;
    a: string;
    b: string;
    delta: string;
    tone: string;
    hint: string;
  }> = [
    {
      label: "Pass rate",
      a: fmtPercent(runA.summary.pass_rate),
      b: fmtPercent(runB.summary.pass_rate),
      delta: signedPoints(comparison.summary.pass_rate_delta),
      tone: deltaClass(comparison.summary.pass_rate_delta),
      hint: "Higher is better",
    },
    {
      label: "Total cost",
      a: fmtCost(runA.summary.total_cost_usd),
      b: fmtCost(runB.summary.total_cost_usd),
      delta: signedCost(comparison.summary.cost_delta_usd),
      tone: deltaClass(comparison.summary.cost_delta_usd, true),
      hint: "Lower is better",
    },
    {
      label: "Avg latency",
      a: fmtLatency(runA.summary.avg_latency_ms),
      b: fmtLatency(runB.summary.avg_latency_ms),
      delta: signedLatency(comparison.summary.latency_delta_ms),
      tone: deltaClass(comparison.summary.latency_delta_ms, true),
      hint: "Lower is better",
    },
    {
      label: "Duration",
      a: `${runA.duration_seconds.toFixed(2)}s`,
      b: `${runB.duration_seconds.toFixed(2)}s`,
      delta: `${comparison.summary.duration_delta_seconds > 0 ? "+" : ""}${comparison.summary.duration_delta_seconds.toFixed(2)}s`,
      tone: deltaClass(comparison.summary.duration_delta_seconds, true),
      hint: "Wall-clock",
    },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <Link href="/evals" className="link link--quiet">
            All evaluations
          </Link>
          <h1 className="page-head__title" style={{ marginTop: "var(--space-xs)" }}>
            Compare evaluations
          </h1>
          <p className="page-head__line">
            {configLine(runA.config)} against {configLine(runB.config)}
          </p>
        </div>
        <div className="page-head__actions">
          <Link href={`/evals/${runA.run_id}`} className="btn btn--quiet">
            Open A
          </Link>
          <Link href={`/evals/${runB.run_id}`} className="btn btn--quiet">
            Open B
          </Link>
        </div>
      </div>

      <div className="compare-grid">
        {[
          { label: "A", run: runA },
          { label: "B", run: runB },
        ].map(({ label, run }) => (
          <div className={`panel${label === "A" ? " panel--lead" : ""}`} key={label}>
            <div className="panel__head">
              <h2 className="panel__title">
                Run {label}, {fmtPercent(run.summary.pass_rate)} pass rate
              </h2>
              <span className="panel__meta">
                {run.summary.passed}/{run.summary.total_tasks} tasks
              </span>
            </div>
            <div className="panel__body compare-card">
              <Link href={`/evals/${run.run_id}`} className="table__task">
                {run.run_id}
              </Link>
              <div className="compare-card__chips">
                <span className="chip chip--muted">
                  {configLine(run.config)}
                </span>
                <span className={`chip ${run.summary.pass_rate >= 0.8 ? "chip--ok" : "chip--amber"}`}>
                  {fmtPercent(run.summary.pass_rate)}
                </span>
              </div>
              <p className="empty__line" style={{ margin: 0 }}>
                {fmtCost(run.summary.total_cost_usd)} total cost,{" "}
                {fmtLatency(run.summary.avg_latency_ms)} average task latency.
              </p>
            </div>
          </div>
        ))}
      </div>

      <section className="final-output">
        <div className="timeline-head">
          <h2>Metric deltas, B against A</h2>
          <span className="panel__meta">
            {comparison.summary.regressions} regressions,{" "}
            {comparison.summary.improvements} improvements
          </span>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num-right">A</th>
                <th className="num-right">B</th>
                <th className="num-right">Change</th>
                <th className="hide-sm">Direction</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric) => (
                <tr key={metric.label}>
                  <td>
                    <span className="table__task">{metric.label}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{metric.a}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{metric.b}</span>
                  </td>
                  <td className="num-right">
                    <span className={metric.tone}>{metric.delta}</span>
                  </td>
                  <td className="hide-sm">
                    <span className="table__id">{metric.hint}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="metrics metrics--three">
        <div className="metric">
          <span className="metric__value">
            {comparison.summary.regressions}
          </span>
          <span className="metric__label">PASS → FAIL regressions</span>
        </div>
        <div className="metric">
          <span className="metric__value">
            {comparison.summary.improvements}
          </span>
          <span className="metric__label">FAIL → PASS improvements</span>
        </div>
        <div className="metric">
          <span className="metric__value">{unchanged.length}</span>
          <span className="metric__label">Tasks without a status change</span>
        </div>
      </div>

      <section className="final-output">
        <div className="timeline-head">
          <h2>Task transitions</h2>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Category</th>
                <th>A</th>
                <th>B</th>
                <th className="num-right">Score delta</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {comparison.rows.map((row) => (
                <tr key={row.task_id}>
                  <td>
                    <span className="table__id">{row.task_id}</span>
                    <span className="table__task">{row.task}</span>
                  </td>
                  <td>
                    <span className="table__id">
                      {categoryLabel(row.category)}
                    </span>
                  </td>
                  <td>
                    {row.a ? (
                      <span className={`chip ${statusTone(row.a.status)}`}>
                        {row.a.status} {row.a.score.toFixed(2)}
                      </span>
                    ) : (
                      <span className="table__id">n/a</span>
                    )}
                  </td>
                  <td>
                    {row.b ? (
                      <span className={`chip ${statusTone(row.b.status)}`}>
                        {row.b.status} {row.b.score.toFixed(2)}
                      </span>
                    ) : (
                      <span className="table__id">n/a</span>
                    )}
                  </td>
                  <td className="num-right">
                    <span
                      className={deltaClass(row.score_delta)}
                    >
                      {row.score_delta > 0 ? "+" : ""}
                      {row.score_delta.toFixed(2)}
                    </span>
                  </td>
                  <td>
                    <span className={`chip ${changeTone(row)}`}>
                      {row.change}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {comparison.regressions.length > 0 ? (
        <section className="final-output">
          <div className="timeline-head">
            <h2>Regressions</h2>
            <span className="panel__meta">blocking for CI</span>
          </div>
          <div className="table-scroll">
            <table className="table table--compact">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Transition</th>
                  <th className="num-right">Score delta</th>
                  <th className="num-right">Latency delta</th>
                </tr>
              </thead>
              <tbody>
                {comparison.regressions.map((row) => (
                  <tr key={row.task_id}>
                    <td>
                      <span className="table__id">{row.task_id}</span>
                    </td>
                    <td>
                      <span className="chip chip--bad">{row.change}</span>
                    </td>
                    <td className="num-right">
                      <span className="table__num">
                        {row.score_delta.toFixed(2)}
                      </span>
                    </td>
                    <td className="num-right">
                      <span className="table__num">
                        {signedLatency(
                          (row.b?.latency_ms ?? 0) - (row.a?.latency_ms ?? 0)
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className="empty" style={{ marginTop: "var(--space-xl)" }}>
          <h2 className="empty__title">No regressions in this comparison</h2>
          <p className="empty__line">
            No task moved from PASS to FAIL. Score changes are still listed in
            the task transitions table above.
          </p>
        </div>
      )}
    </>
  );
}

export default function CompareEvalsPage({
  params,
}: {
  params: Promise<{ a: string; b: string }>;
}) {
  return (
    <div className="shell page">
      <Suspense fallback={<p className="empty__line">Loading comparison…</p>}>
        <CompareContent params={params} />
      </Suspense>
    </div>
  );
}
