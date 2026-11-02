"use client";
import type { ReactNode } from "react";
import type { StepType } from "@/lib/api";

// --- shared design primitives ---------------------------------------------
// Kept tiny and dependency-free so the CI build stays clean. All colored
// surfaces are Tailwind; the accent system lives in globals.css.

export const PHASE_COLOR: Record<StepType, { dot: string; text: string; bar: string }> = {
  plan: { dot: "bg-indigo-400", text: "text-indigo-300", bar: "bg-indigo-400/70" },
  tool_call: { dot: "bg-sky-400", text: "text-sky-300", bar: "bg-sky-400/70" },
  llm_call: { dot: "bg-teal-400", text: "text-teal-300", bar: "bg-teal-400/70" },
  critique: { dot: "bg-amber-400", text: "text-amber-300", bar: "bg-amber-400/70" },
  revision: { dot: "bg-fuchsia-400", text: "text-fuchsia-300", bar: "bg-fuchsia-400/70" },
};

export function Card({ children, className = "", glow = false }: { children: ReactNode; className?: string; glow?: boolean }) {
  return (
    <div className={`rounded-xl border border-neutral-800 bg-neutral-950/40 ${glow ? "glow" : ""} ${className}`}>{children}</div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-neutral-500">{children}</div>;
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    succeeded: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
    running: "bg-amber-500/10 text-amber-300 border-amber-500/20",
    failed: "bg-red-500/10 text-red-300 border-red-500/20",
    timeout: "bg-orange-500/10 text-orange-300 border-orange-500/20",
  };
  const dot: Record<string, string> = {
    succeeded: "bg-emerald-400",
    running: "bg-amber-400",
    failed: "bg-red-400",
    timeout: "bg-orange-400",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] ${map[status] ?? "bg-neutral-800 text-neutral-300 border-neutral-700"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot[status] ?? "bg-neutral-400"}`} />
      {status}
    </span>
  );
}

export function ModelChip({ provider, model }: { provider: string | null; model: string | null }) {
  if (!provider && !model) return <span className="font-mono text-xs text-neutral-600">—</span>;
  return (
    <span className="rounded-md border border-neutral-800 bg-neutral-900 px-1.5 py-0.5 font-mono text-[11px] text-neutral-300">
      <span className="text-neutral-500">{provider}</span>
      <span className="mx-1 text-neutral-700">/</span>
      {model}
    </span>
  );
}

// A thin horizontal bar - used for cost + latency micro-visuals
export function Bar({ value, max, tone = "bg-accent" }: { value: number; max: number; tone?: string }) {
  const pct = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-neutral-800">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

// Legend explaining the timeline's phase dots - the "read the trace in 30s" anchor
const PHASE_LABEL: Record<StepType, string> = {
  plan: "planner",
  tool_call: "tool",
  llm_call: "reasoning",
  critique: "critic",
  revision: "reviser",
};
export function PhaseLegend() {
  const order: StepType[] = ["plan", "tool_call", "llm_call", "critique", "revision"];
  return (
    <div className="flex flex-wrap items-center gap-3">
      {order.map((t) => (
        <span key={t} className="flex items-center gap-1.5 font-mono text-[10px] text-neutral-500">
          <span className={`h-2 w-2 rounded-full ${PHASE_COLOR[t].dot}`} />
          {PHASE_LABEL[t]}
        </span>
      ))}
    </div>
  );
}

// +/-% delta with a "is this good" color (lower is better here)
export function Delta({ from, to, unit = "" }: { from: number; to: number; unit?: string }) {
  if (from === 0 && to === 0) return <span className="font-mono text-xs text-neutral-600">—</span>;
  const pct = from === 0 ? 100 : ((to - from) / from) * 100;
  const better = to < from;
  const same = Math.abs(pct) < 0.05;
  return (
    <span className={`font-mono text-xs ${same ? "text-neutral-500" : better ? "text-emerald-300" : "text-amber-300"}`}>
      {pct > 0 ? "+" : ""}{pct.toFixed(1)}%{unit}
    </span>
  );
}
