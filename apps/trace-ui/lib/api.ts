// Minimal typed client for the agent API. The trace viewer runs in the browser
// (Next on :3000) and talks directly to the API (:8000) - CORS is enabled there.
// base URL is baked from NEXT_PUBLIC_API_URL (compose sets it; local dev falls
// back to :8000).
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type StepType = "plan" | "tool_call" | "llm_call" | "critique" | "revision";

export interface Step {
  step_id: string;
  parent_step_id: string | null;
  type: StepType;
  name: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: string | null;
  latency_ms: number;
  tokens: { in: number; out: number };
  cost_usd: number;
}

export interface Run {
  run_id: string;
  task: string;
  status: "running" | "succeeded" | "failed" | "timeout";
  provider: string | null;
  model: string | null;
  created_at: string;
  final_output: { answer: string; artifacts: string[] } | null;
  steps: Step[];
}

export interface RunSummary {
  run_id: string;
  task: string;
  status: Run["status"];
  provider: string | null;
  model: string | null;
  created_at: string;
  cost_usd: number;
  duration_ms: number;
  n_steps: number;
}

export interface CostBreakdown {
  total: number;
  per_type: { type: StepType; count: number; cost: number; ms: number; tokens: number }[];
}
export function breakdownCost(steps: Step[]): CostBreakdown {
  const byType = new Map<StepType, { cost: number; ms: number; tokens: number }>();
  for (const s of steps) {
    const b = byType.get(s.type) ?? { cost: 0, ms: 0, tokens: 0 };
    b.cost += s.cost_usd ?? 0;
    b.ms += s.latency_ms ?? 0;
    b.tokens += (s.tokens?.in ?? 0) + (s.tokens?.out ?? 0);
    byType.set(s.type, b);
  }
  return {
    total: steps.reduce((a, s) => a + (s.cost_usd ?? 0), 0),
    per_type: [...byType.entries()].map(([type, b]) => ({
      type,
      ...b,
      count: steps.filter((s) => s.type === type).length,
    })),
  };
}

export interface Config {
  default_provider: string;
  default_model: string;
  providers: Record<string, string[]>;
  api_keys: Record<string, boolean>;
}

export interface ArtifactRef {
  name: string;
  size: number;
  truncated?: boolean;
}

// --- fetch helpers ---------------------------------------------------------
async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return (await r.json()) as T;
}

export const listRuns = (limit = 50) => getJson<RunSummary[]>(`/runs?limit=${limit}`);
export const getRun = (id: string) => getJson<Run>(`/runs/${id}`);
export const getConfig = () => getJson<Config>("/config");
export const artifactUrl = (path: string) => `${API}${path}`;

// Re-run a task, optionally with a different provider/model (replay).
export async function replayRun(
  task: string,
  provider?: string,
  model?: string
): Promise<Run> {
  const r = await fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, provider: provider || null, model: model || null }),
  });
  if (!r.ok) throw new Error(`POST /runs -> ${r.status}`);
  return (await r.json()) as Run;
}

// --- small formatting helpers used across the UI -------------------------
export function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}
export function fmtUsd(v: number): string {
  return v === 0 ? "$0.00" : `$${v.toFixed(4)}`;
}
export function fmtTok(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}
export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86_400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
export function stepArtifacts(input: Step["input"]): ArtifactRef[] {
  const to = (input?.tool_output as { artifacts?: ArtifactRef[] } | undefined)?.artifacts;
  return Array.isArray(to) ? to : [];
}
