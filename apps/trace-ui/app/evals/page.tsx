import Link from "next/link";
import {
  configLine,
  fmtCost,
  fmtLatency,
  fmtPercent,
  listEvalReports,
} from "@/lib/evals";
import { RelativeTime } from "@/components/RelativeTime";

function rateTone(rate: number): string {
  if (rate >= 0.8) return "chip--ok";
  if (rate > 0) return "chip--amber";
  return "chip--bad";
}

export default function EvalsPage() {
  const evals = listEvalReports();
  const latest = evals[0];
  const previous = evals[1];

  return (
    <div className="shell page">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Evaluation results</h1>
          <p className="page-head__line">
            Deterministic golden-task runs: nine tasks, seven scorers, config
            hashing, and regression detection across versions.
          </p>
          <p className="page-head__meta">
            {evals.length} {evals.length === 1 ? "committed run" : "committed runs"}
          </p>
        </div>
        <div className="page-head__actions">
          {latest && previous ? (
            <Link
              href={`/evals/compare/${previous.run_id}/${latest.run_id}`}
              className="btn btn--primary"
            >
              Compare latest two
            </Link>
          ) : null}
          <Link href="/docs/evaluation" className="btn btn--quiet">
            Evaluation method
          </Link>
        </div>
      </div>

      <section className="panel" style={{ marginBottom: "var(--space-xl)" }}>
        <div className="panel__head">
          <h2 className="panel__title">How a run is scored</h2>
          <span className="panel__meta">deterministic</span>
        </div>
        <div className="panel__body">
          <div className="metrics metrics--three">
            <div className="metric">
              <span className="metric__value">9</span>
              <span className="metric__label">Golden tasks, 3 categories</span>
            </div>
            <div className="metric">
              <span className="metric__value">7</span>
              <span className="metric__label">Deterministic scorers</span>
            </div>
            <div className="metric">
              <span className="metric__value">80%</span>
              <span className="metric__label">Check threshold plus schema gate</span>
            </div>
          </div>
          <p className="empty__line" style={{ marginTop: "var(--space-md)" }}>
            A task passes only when its JSON schema validates and at least 80% of
            its remaining checks pass. The overall score is the mean of the
            schema score and the check pass fraction. Each run is identified by
            a hash of its config, so regression comparisons are reproducible.
          </p>
          <p className="empty__line">
            These committed runs use the deterministic mock executor in{" "}
            <span className="empty__path">packages/eval/runner.py</span>. Identical
            scores across configs are expected until{" "}
            <span className="empty__path">run_task()</span> is wired to the live
            agent executor.
          </p>
        </div>
      </section>

      {evals.length === 0 ? (
        <div className="empty">
          <h2 className="empty__title">No evaluation reports yet</h2>
          <p className="empty__line">
            Run <span className="empty__path">make eval-run</span> to create a
            golden-task report. Committed reports appear here once the run
            finishes.
          </p>
          <div className="empty__actions">
            <Link href="/docs/eval-quickstart" className="btn btn--primary">
              Evaluation quick start
            </Link>
          </div>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Config</th>
                <th className="num-right">Pass rate</th>
                <th className="hide-sm num-right">Passed</th>
                <th className="hide-sm num-right">Cost</th>
                <th className="hide-sm num-right">Avg latency</th>
                <th className="num-right">Recorded</th>
                <th className="num-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {evals.map((report) => (
                <tr key={report.run_id}>
                  <td>
                    <Link
                      href={`/evals/${report.run_id}`}
                      className="table__task"
                    >
                      {report.run_id}
                    </Link>
                  </td>
                  <td>
                    <span className="table__id">
                      {configLine(report.config)}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className={`chip ${rateTone(report.summary.pass_rate)}`}>
                      {fmtPercent(report.summary.pass_rate)}
                    </span>
                  </td>
                  <td className="hide-sm num-right">
                    <span className="table__num">
                      {report.summary.passed}/{report.summary.total_tasks}
                    </span>
                  </td>
                  <td className="hide-sm num-right">
                    <span className="table__num">
                      {fmtCost(report.summary.total_cost_usd)}
                    </span>
                  </td>
                  <td className="hide-sm num-right">
                    <span className="table__num">
                      {fmtLatency(report.summary.avg_latency_ms)}
                    </span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">
                      <RelativeTime iso={report.timestamp} />
                    </span>
                  </td>
                  <td className="num-right">
                    {latest && report.run_id !== latest.run_id ? (
                      <Link
                        href={`/evals/compare/${report.run_id}/${latest.run_id}`}
                        className="table__action"
                      >
                        Compare to latest
                      </Link>
                    ) : (
                      <Link
                        href={`/evals/${report.run_id}`}
                        className="table__action"
                      >
                        Open
                      </Link>
                    )}
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
