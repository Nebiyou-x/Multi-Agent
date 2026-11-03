import { Suspense } from "react";
import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import Link from "next/link";
import { RelativeTime } from "@/components/RelativeTime";

interface TraceFile {
  name: string;
  task: string;
  runId: string;
  timestamp: string;
}

function listTraces(): TraceFile[] {
  try {
    const tracesDir = join(process.cwd(), "reports", "traces");
    const files = readdirSync(tracesDir).filter((f) => f.endsWith(".json"));

    return files
      .map((file) => {
        try {
          const content = readFileSync(join(tracesDir, file), "utf-8");
          const data = JSON.parse(content);
          return {
            name: file.replace(".json", ""),
            task: data.task || "Untitled",
            runId: data.run_id || file.replace(".json", ""),
            timestamp: data.timestamp || new Date().toISOString(),
          };
        } catch {
          return null;
        }
      })
      .filter((x): x is TraceFile => x !== null);
  } catch {
    return [];
  }
}

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