// Server-only loader for committed evaluation reports. The evaluator writes
// JSON to data/eval_results/ at the repo root; the UI also accepts reports
// copied into apps/trace-ui/reports/evals/ (useful for the Docker image, where
// runtime data is not part of the build context).
import { readdirSync, readFileSync, statSync } from "fs";
import { join } from "path";

export type EvalStatus = "PASS" | "FAIL" | "ERROR";

export interface EvalCheck {
  scorer: string;
  passed: boolean;
  score: number;
  details: string;
}

export interface EvalTaskResult {
  task_id: string;
  task: string;
  category: string;
  status: EvalStatus;
  score: number;
  details: EvalCheck[];
  cost_usd: number;
  latency_ms: number;
  error: string | null;
  output: string | null;
}

export interface EvalCategorySummary {
  passed: number;
  failed: number;
  errors: number;
  avg_score: number;
}

export interface EvalSummary {
  total_tasks: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
  avg_cost_usd: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  by_category: Record<string, EvalCategorySummary>;
}

export interface EvalReport {
  run_id: string;
  config_hash: string;
  config: Record<string, unknown>;
  dataset: string;
  timestamp: string;
  duration_seconds: number;
  results: EvalTaskResult[];
  summary: EvalSummary;
}

export interface EvalTaskComparison {
  task_id: string;
  task: string;
  category: string;
  a: EvalTaskResult | null;
  b: EvalTaskResult | null;
  change: string;
  score_delta: number;
  regression: boolean;
  improvement: boolean;
}

export interface EvalComparison {
  a: EvalReport;
  b: EvalReport;
  rows: EvalTaskComparison[];
  regressions: EvalTaskComparison[];
  improvements: EvalTaskComparison[];
  summary: {
    total_tasks: number;
    regressions: number;
    improvements: number;
    pass_rate_delta: number;
    cost_delta_usd: number;
    latency_delta_ms: number;
    duration_delta_seconds: number;
  };
}

type RawObject = Record<string, unknown>;

const CANDIDATE_DIRS = [
  process.env.EVALS_DIR,
  join(process.cwd(), "reports", "evals"),
  join(process.cwd(), "data", "eval_results"),
  join(process.cwd(), "..", "..", "data", "eval_results"),
].filter((dir): dir is string => Boolean(dir));

function isDirectory(dir: string): boolean {
  try {
    return statSync(dir).isDirectory();
  } catch {
    return false;
  }
}

function readJson(file: string): RawObject | null {
  try {
    return JSON.parse(readFileSync(file, "utf-8")) as RawObject;
  } catch {
    return null;
  }
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function normalizeStatus(value: unknown, passed: unknown): EvalStatus {
  if (value === "PASS" || value === "FAIL" || value === "ERROR") return value;
  if (passed === true) return "PASS";
  if (passed === false) return "FAIL";
  return "ERROR";
}

function normalizeCheck(raw: unknown): EvalCheck {
  const item = (raw ?? {}) as RawObject;
  return {
    scorer: asString(item.scorer ?? item.scorer_name, "check"),
    passed: item.passed === true,
    score: asNumber(item.score),
    details: asString(item.details ?? item.detail, ""),
  };
}

export function summarizeResults(results: EvalTaskResult[]): EvalSummary {
  const passed = results.filter((r) => r.status === "PASS").length;
  const failed = results.filter((r) => r.status === "FAIL").length;
  const errors = results.filter((r) => r.status === "ERROR").length;
  const byCategory: Record<string, EvalCategorySummary> = {};

  for (const result of results) {
    const bucket =
      byCategory[result.category] ??
      (byCategory[result.category] = {
        passed: 0,
        failed: 0,
        errors: 0,
        avg_score: 0,
      });
    if (result.status === "PASS") bucket.passed += 1;
    else if (result.status === "FAIL") bucket.failed += 1;
    else bucket.errors += 1;
  }

  for (const [category, bucket] of Object.entries(byCategory)) {
    const scores = results
      .filter((r) => r.category === category)
      .map((r) => r.score);
    bucket.avg_score =
      scores.length > 0
        ? scores.reduce((sum, score) => sum + score, 0) / scores.length
        : 0;
  }

  const totalCost = results.reduce((sum, result) => sum + result.cost_usd, 0);
  const totalLatency = results.reduce((sum, result) => sum + result.latency_ms, 0);
  const total = results.length;

  return {
    total_tasks: total,
    passed,
    failed,
    errors,
    pass_rate: total > 0 ? passed / total : 0,
    avg_cost_usd: total > 0 ? totalCost / total : 0,
    total_cost_usd: totalCost,
    avg_latency_ms: total > 0 ? totalLatency / total : 0,
    by_category: byCategory,
  };
}

function normalizeReport(raw: RawObject, fallbackId: string): EvalReport {
  const rawResults = Array.isArray(raw.results) ? raw.results : [];
  const results: EvalTaskResult[] = rawResults.map((entry, index) => {
    const result = (entry ?? {}) as RawObject;
    const status = normalizeStatus(result.status, result.passed);
    const details = Array.isArray(result.details)
      ? result.details.map(normalizeCheck)
      : [];

    // Old sample reports carried one scorer per row instead of a details list.
    if (details.length === 0 && typeof result.passed === "boolean") {
      details.push({
        scorer: asString(result.scorer, "check"),
        passed: result.passed,
        score: asNumber(result.score, result.passed ? 1 : 0),
        details: asString(result.detail, ""),
      });
    }

    return {
      task_id: asString(result.task_id ?? result.id, `task_${index + 1}`),
      task: asString(result.task ?? result.name, "Untitled task"),
      category: asString(result.category, "general"),
      status,
      score: asNumber(result.score),
      details,
      cost_usd: asNumber(result.cost_usd ?? result.cost),
      latency_ms: asNumber(result.latency_ms ?? result.latency),
      error: typeof result.error === "string" ? result.error : null,
      output:
        typeof result.output === "string"
          ? result.output
          : result.output
            ? JSON.stringify(result.output)
            : null,
    };
  });

  const rawConfig = raw.config;
  const config =
    rawConfig && typeof rawConfig === "object" && !Array.isArray(rawConfig)
      ? (rawConfig as Record<string, unknown>)
      : { model: asString(raw.model, "unknown") };

  return {
    run_id: asString(raw.run_id ?? raw.config_hash, fallbackId),
    config_hash: asString(raw.config_hash, "n/a"),
    config,
    dataset: asString(raw.dataset, "golden-9"),
    timestamp: asString(raw.timestamp, new Date(0).toISOString()),
    duration_seconds: asNumber(raw.duration_seconds),
    results,
    summary: summarizeResults(results),
  };
}

function loadReportFile(file: string, fallbackId: string): EvalReport | null {
  const raw = readJson(file);
  return raw ? normalizeReport(raw, fallbackId) : null;
}

export function listEvalReports(): EvalReport[] {
  const seen = new Set<string>();
  const reports: EvalReport[] = [];

  for (const dir of CANDIDATE_DIRS) {
    if (!isDirectory(dir)) continue;

    let entries: string[] = [];
    try {
      entries = readdirSync(dir);
    } catch {
      continue;
    }

    for (const entry of entries) {
      if (!entry.endsWith(".json") || entry.startsWith("comparison_")) continue;
      const report = loadReportFile(
        join(dir, entry),
        entry.replace(/\.json$/, "")
      );
      if (!report || seen.has(report.run_id)) continue;
      seen.add(report.run_id);
      reports.push(report);
    }
  }

  return reports.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

export function getEvalReport(runId: string): EvalReport | null {
  // Prevent path traversal from the dynamic route.
  if (!/^[A-Za-z0-9._-]+$/.test(runId)) return null;
  return listEvalReports().find((report) => report.run_id === runId) ?? null;
}

export function compareEvalReports(
  runA: EvalReport,
  runB: EvalReport
): EvalComparison {
  const byTaskA = new Map(runA.results.map((result) => [result.task_id, result]));
  const byTaskB = new Map(runB.results.map((result) => [result.task_id, result]));
  const taskIds = [
    ...runA.results.map((result) => result.task_id),
    ...runB.results
      .map((result) => result.task_id)
      .filter((taskId) => !byTaskA.has(taskId)),
  ];

  const rows: EvalTaskComparison[] = taskIds.map((taskId) => {
    const a = byTaskA.get(taskId) ?? null;
    const b = byTaskB.get(taskId) ?? null;

    let change = "unchanged";
    let regression = false;
    let improvement = false;

    if (a && b) {
      if (a.status === "PASS" && b.status !== "PASS") {
        change = `PASS → ${b.status}`;
        regression = true;
      } else if (a.status !== "PASS" && b.status === "PASS") {
        change = `${a.status} → PASS`;
        improvement = true;
      } else if (a.status !== b.status) {
        change = `${a.status} → ${b.status}`;
      }
    } else if (!a) {
      change = "added";
    } else if (!b) {
      change = "removed";
    }

    return {
      task_id: taskId,
      task: b?.task ?? a?.task ?? taskId,
      category: b?.category ?? a?.category ?? "general",
      a,
      b,
      change,
      score_delta: (b?.score ?? 0) - (a?.score ?? 0),
      regression,
      improvement,
    };
  });

  return {
    a: runA,
    b: runB,
    rows,
    regressions: rows.filter((row) => row.regression),
    improvements: rows.filter((row) => row.improvement),
    summary: {
      total_tasks: rows.length,
      regressions: rows.filter((row) => row.regression).length,
      improvements: rows.filter((row) => row.improvement).length,
      pass_rate_delta: runB.summary.pass_rate - runA.summary.pass_rate,
      cost_delta_usd: runB.summary.total_cost_usd - runA.summary.total_cost_usd,
      latency_delta_ms: runB.summary.avg_latency_ms - runA.summary.avg_latency_ms,
      duration_delta_seconds: runB.duration_seconds - runA.duration_seconds,
    },
  };
}

export function configLine(config: Record<string, unknown>): string {
  const entries = Object.entries(config);
  if (entries.length === 0) return "default";
  return entries
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
}

export function categoryLabel(category: string): string {
  return category.replace(/_/g, " ");
}

export function fmtPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

export function fmtLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
