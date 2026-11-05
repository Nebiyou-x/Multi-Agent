import { Suspense } from "react";
import Link from "next/link";
import { RelativeTime } from "@/components/RelativeTime";
import { listTraces } from "@/lib/traces";

export default function TracesPage() {
  const traces = listTraces();

  return (
    <div className="shell page">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Traces</h1>
          <p className="page-head__line">
            Committed trace reports show every step: plans, tool calls, LLM outputs, critiques, and revisions.
          </p>
          <p className="page-head__meta">
            {traces.length} {traces.length === 1 ? "committed trace" : "committed traces"}
          </p>
        </div>
      </div>

      {traces.length === 0 ? (
        <div className="empty">
          <h2 className="empty__title">No traces yet</h2>
          <p className="empty__line">Generate traces by running Agent Forge tasks.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Report</th>
                <th>Task</th>
                <th className="num-right">Recorded</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((trace) => (
                <tr key={trace.runId}>
                  <td>
                    <span className="table__id">{trace.name}</span>
                  </td>
                  <td>
                    <Link href={`/traces/${trace.runId}`} className="table__task">
                      {trace.task}
                    </Link>
                  </td>
                  <td className="num-right">
                    <span className="table__num">
                      <Suspense fallback={<span>—</span>}>
                        <RelativeTime iso={trace.timestamp} />
                      </Suspense>
                    </span>
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