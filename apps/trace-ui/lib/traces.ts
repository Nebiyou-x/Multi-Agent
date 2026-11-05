import { readdirSync, readFileSync } from "fs";
import { join } from "path";

interface TraceStep {
  cost_usd?: number;
  latency_ms?: number;
}

interface TraceReport {
  run_id: string;
  task: string;
  status: string;
  timestamp: string;
  steps: TraceStep[];
}

export interface TraceSummary {
  name: string;
  task: string;
  runId: string;
  status: string;
  timestamp: string;
  costUsd: number;
  durationMs: number;
  stepCount: number;
}

export function listTraces(): TraceSummary[] {
  const tracesDir = join(process.cwd(), "reports", "traces");

  return readdirSync(tracesDir)
    .filter((file) => file.endsWith(".json"))
    .map((file) => {
      const report = JSON.parse(
        readFileSync(join(tracesDir, file), "utf-8"),
      ) as TraceReport;

      return {
        name: file.replace(/\.json$/, ""),
        task: report.task,
        runId: report.run_id,
        status: report.status,
        timestamp: report.timestamp,
        costUsd: report.steps.reduce((sum, step) => sum + (step.cost_usd ?? 0), 0),
        durationMs: report.steps.reduce(
          (sum, step) => sum + (step.latency_ms ?? 0),
          0,
        ),
        stepCount: report.steps.length,
      };
    })
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
}
