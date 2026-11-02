import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import Link from "next/link";
import { formatDistanceToNow, parseISO } from "date-fns";

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
      .filter(Boolean) as TraceFile[];
  } catch {
    return [];
  }
}

export default function TracesPage() {
  const traces = listTraces();

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Traces</h1>
        <p className="text-neutral-400">
          Committed trace reports show every step: plans, tool calls, LLM outputs, critiques, and revisions.
        </p>
      </div>

      {traces.length === 0 ? (
        <div className="rounded-lg border border-neutral-800 p-8 text-center">
          <p className="text-neutral-400">No traces yet. Generate traces by running Agent Forge tasks.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {traces.map((trace) => (
            <Link
              key={trace.runId}
              href={`/traces/${trace.runId}`}
              className="group p-6 rounded-lg border border-neutral-800 bg-neutral-950/40 hover:border-indigo-600/50 hover:bg-neutral-900/60 transition-all"
            >
              <div className="font-mono text-xs text-neutral-500 mb-2">{trace.name}</div>
              <h3 className="font-semibold text-lg group-hover:text-indigo-300 transition-colors mb-2 line-clamp-2">
                {trace.task}
              </h3>
              <div className="text-xs text-neutral-500">
                {formatDistanceToNow(parseISO(trace.timestamp), { addSuffix: true })}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
