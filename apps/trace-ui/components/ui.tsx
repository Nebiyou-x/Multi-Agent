"use client";

import type { ReactNode } from "react";
import type { StepType } from "@/lib/api";

export const PHASE_COLOR: Record<StepType, { swatch: string; chip: string; bar: string }> = {
  plan: { swatch: "swatch--cool", chip: "chip--cool", bar: "bar-fill--cool" },
  tool_call: { swatch: "swatch--cool", chip: "chip--cool", bar: "bar-fill--cool" },
  llm_call: { swatch: "swatch--cool", chip: "chip--cool", bar: "bar-fill--cool" },
  critique: { swatch: "swatch--amber", chip: "chip--amber", bar: "bar-fill--amber" },
  revision: { swatch: "swatch--amber", chip: "chip--amber", bar: "bar-fill--amber" },
};

export function Card({
  children,
  className = "",
  glow = false,
}: {
  children: ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return <div className={`panel${glow ? " panel--lead" : ""} ${className}`.trim()}>{children}</div>;
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="label">{children}</div>;
}

export function StatusPill({ status }: { status: string }) {
  const tone =
    status === "succeeded"
      ? "chip--ok"
      : status === "failed"
        ? "chip--bad"
        : status === "running"
          ? "chip--amber"
          : "chip--muted";
  return <span className={`chip ${tone}`}>{status}</span>;
}

export function ModelChip({ provider, model }: { provider: string | null; model: string | null }) {
  if (!provider && !model) return <span className="meta__value">n/a</span>;
  return (
    <span className="chip chip--muted">
      <span className="mono">{provider ?? "n/a"}</span>
      <span className="chip__sep">/</span>
      <span className="mono">{model ?? "n/a"}</span>
    </span>
  );
}

export function Bar({
  value,
  max,
  tone = "bar-fill--cool",
}: {
  value: number;
  max: number;
  tone?: string;
}) {
  const pct = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="bar" aria-hidden="true">
      <div className={`bar__fill ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

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
    <div className="phase-legend">
      {order.map((type) => (
        <span key={type} className="phase-legend__item">
          <span className={`swatch ${PHASE_COLOR[type].swatch}`} aria-hidden="true" />
          {PHASE_LABEL[type]}
        </span>
      ))}
    </div>
  );
}

export function Delta({ from, to, unit = "" }: { from: number; to: number; unit?: string }) {
  if (from === 0 && to === 0) return <span className="delta delta--same">n/a</span>;
  const pct = from === 0 ? 100 : ((to - from) / from) * 100;
  const better = to < from;
  const same = Math.abs(pct) < 0.05;
  return (
    <span className={`delta ${same ? "delta--same" : better ? "delta--ok" : "delta--bad"}`}>
      {pct > 0 ? "+" : ""}
      {pct.toFixed(1)}%{unit}
    </span>
  );
}
