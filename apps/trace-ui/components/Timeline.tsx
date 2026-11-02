"use client";

import { useState } from "react";
import type { Step, StepType } from "@/lib/api";
import { API, fmtMs, fmtUsd, fmtTok } from "@/lib/api";
import { highlight } from "@/lib/highlight";
import { diffWords, type DiffPart } from "@/lib/diff";
import { PHASE_COLOR, Bar } from "@/components/ui";

interface Node {
  step: Step;
  children: Node[];
}
function buildTree(steps: Step[]): Node[] {
  const nodes = new Map<string, Node>();
  steps.forEach((s) => nodes.set(s.step_id, { step: s, children: [] }));
  const roots: Node[] = [];
  for (const s of steps) {
    const node = nodes.get(s.step_id)!;
    if (s.parent_step_id && nodes.has(s.parent_step_id)) nodes.get(s.parent_step_id)!.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function isImage(name: string) {
  return /\.(png|jpe?g|gif|svg|webp|bmp|ico)$/i.test(name);
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2 py-0.5 text-[11px]">
      <span className="w-16 shrink-0 text-neutral-500">{k}</span>
      <span className="text-neutral-300 tabular-nums">{v}</span>
    </div>
  );
}

function MetaBlock({ step }: { step: Step }) {
  const t = step.tokens ?? { in: 0, out: 0 };
  return (
    <div>
      <KV k="tokens in" v={fmtTok(t.in)} />
      <KV k="tokens out" v={fmtTok(t.out)} />
      <KV k="cost" v={fmtUsd(step.cost_usd ?? 0)} />
      <KV k="latency" v={fmtMs(step.latency_ms ?? 0)} />
      <KV k="step id" v={step.step_id.slice(0, 8)} />
    </div>
  );
}

type ToolOut = Record<string, unknown>;
const toOf = (step: Step): ToolOut => ((step.input?.tool_output ?? {}) as ToolOut) || {};

function OutputView({ step, runId }: { step: Step; runId: string }) {
  const out = (step.output ?? {}) as Record<string, unknown>;
  const to = toOf(step);

  if (step.type === "critique") {
    const v = out as { verdict?: string; feedback?: string; score?: number };
    return (
      <div className="space-y-2 text-[13px]">
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 font-mono text-xs font-medium ${
              v.verdict === "PASS" ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"
            }`}
          >
            {v.verdict ?? "—"}
          </span>
          {typeof v.score === "number" && (
            <span className="text-neutral-400">
              confidence <span className="font-mono tabular-nums">{(v.score * 100).toFixed(0)}%</span>
            </span>
          )}
        </div>
        {v.feedback && <p className="whitespace-pre-wrap text-neutral-300">{v.feedback}</p>}
      </div>
    );
  }
  if (step.type === "revision" && typeof out.revised === "string")
    return <p className="whitespace-pre-wrap text-[13px] text-neutral-300">{out.revised}</p>;

  const artifacts = (Array.isArray(to.artifacts) ? to.artifacts : []) as {
    name: string;
    size: number;
    truncated?: boolean;
  }[];

  if (artifacts.length > 0)
    return (
      <div className="grid grid-cols-2 gap-2">
        {artifacts.map((a) => (
          <a
            key={a.name}
            href={`${API}/artifacts/${runId}/${a.name}`}
            target="_blank"
            rel="noreferrer"
            className="group/art rounded-lg border border-neutral-800 bg-neutral-900/60 p-2 transition-colors hover:border-neutral-700"
          >
            {isImage(a.name) ? (
              <img
                src={`${API}/artifacts/${runId}/${a.name}`}
                alt={a.name}
                className="max-h-44 w-full rounded bg-neutral-950 object-contain"
              />
            ) : (
              <div className="grid h-16 place-items-center rounded bg-neutral-950 font-mono text-xs text-neutral-500">
                {a.name.split(".").pop()?.toUpperCase()}
              </div>
            )}
            <div className="mt-1.5 flex justify-between text-[10px] text-neutral-500">
              <span className="truncate">{a.name}</span>
              <span className="tabular-nums">{a.truncated ? "truncated" : `${(a.size / 1024).toFixed(1)} KB`}</span>
            </div>
          </a>
        ))}
      </div>
    );

  if (typeof out.result === "string")
    return <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-neutral-300">{out.result}</p>;

  return (
    <pre className="code-scroll max-h-64 overflow-auto rounded bg-neutral-950 p-2 text-neutral-300">
      {highlight(JSON.stringify(step.output ?? {}, null, 2), "json")}
    </pre>
  );
}

function StepRow({
  node,
  depth,
  open,
  onOpen,
  runId,
  maxCost,
}: {
  node: Node;
  depth: number;
  open: boolean;
  onOpen: () => void;
  runId: string;
  maxCost: number;
}) {
  const s = node.step;
  const color = PHASE_COLOR[s.type] ?? PHASE_COLOR.llm_call;
  const [tab, setTab] = useState<"output" | "input" | "meta">("output");
  const inAny = (s.input ?? {}) as Record<string, unknown>;
  const to = toOf(s);
  const codeSrc = typeof to.code === "string" ? to.code : null;
  const sqlSrc = s.name === "sql_query" ? (((to.query as string) || (inAny.query as string) || "").trim() || null) : null;

  return (
    <div className={depth > 0 ? "ml-5 border-l border-neutral-800 pl-4" : ""}>
      <button
        onClick={onOpen}
        className={`group flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors ${
          open ? "bg-neutral-900/80" : "hover:bg-neutral-900/50"
        }`}
      >
        <span className="relative flex w-4 justify-center">
          <span className={`h-2.5 w-2.5 rounded-full ${color.dot} ${open ? "ring-4 ring-neutral-800" : ""}`} />
        </span>
        <span className="font-mono text-xs font-medium text-neutral-200">{s.name}</span>
        <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${color.text} bg-neutral-900`}>
          {s.type.replace("_call", "")}
        </span>
        {s.error && (
          <span className="rounded bg-red-500/10 px-1.5 py-0.5 font-mono text-[10px] text-red-300">error</span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-3">
          <span className="w-20">
            <Bar value={s.cost_usd ?? 0} max={maxCost} tone={color.bar} />
          </span>
          <span className="w-14 text-right font-mono text-[11px] tabular-nums text-neutral-500">
            {fmtUsd(s.cost_usd ?? 0)}
          </span>
          <span className="w-12 text-right font-mono text-[11px] tabular-nums text-neutral-600">
            {fmtMs(s.latency_ms ?? 0)}
          </span>
          <span className={`font-mono text-[10px] transition-transform ${open ? "text-neutral-400" : "text-neutral-700"}`}>
            {open ? "▾" : "▸"}
          </span>
        </span>
      </button>

      {open && (
        <div className="mb-2 ml-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-3">
          <div className="mb-2 flex items-center gap-1">
            {(["output", "input", "meta"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors ${
                  tab === t ? "bg-neutral-800 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === "meta" && <MetaBlock step={s} />}

          {tab === "input" && (
            <div className="space-y-2">
              {codeSrc && (
                <div>
                  <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-neutral-600">
                    generated code
                  </div>
                  <pre className="code-scroll max-h-60 overflow-auto rounded-lg bg-neutral-950 p-2.5">
                    {highlight(codeSrc, "python")}
                  </pre>
                </div>
              )}
              {sqlSrc && (
                <div>
                  <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-neutral-600">sql</div>
                  <pre className="code-scroll max-h-40 overflow-auto rounded-lg bg-neutral-950 p-2.5">
                    {highlight(sqlSrc, "sql")}
                  </pre>
                </div>
              )}
              {!codeSrc && !sqlSrc && (
                <pre className="code-scroll max-h-40 overflow-auto rounded-lg bg-neutral-950 p-2.5 text-[12px]">
                  {highlight(JSON.stringify(s.input ?? {}, null, 2), "json")}
                </pre>
              )}
            </div>
          )}

          {tab === "output" && <OutputView step={s} runId={runId} />}

          {s.error && (
            <div className="mt-2 rounded-lg border border-red-900/50 bg-red-950/30 p-2.5">
              <div className="mb-0.5 font-mono text-[10px] uppercase tracking-wide text-red-400">error</div>
              <p className="whitespace-pre-wrap font-mono text-xs text-red-300">{s.error}</p>
            </div>
          )}
        </div>
      )}

      {open && node.children.length > 0 && (
        <div className="ml-4">
          {node.children.map((c) => (
            <ChildRow key={c.step.step_id} node={c} depth={depth + 1} runId={runId} maxCost={maxCost} />
          ))}
        </div>
      )}
    </div>
  );
}

function ChildRow({
  node,
  depth,
  runId,
  maxCost,
}: {
  node: Node;
  depth: number;
  runId: string;
  maxCost: number;
}) {
  const [open, setOpen] = useState(false);
  return <StepRow node={node} depth={depth} open={open} onOpen={() => setOpen((o) => !o)} runId={runId} maxCost={maxCost} />;
}

export default function Timeline({ steps, runId }: { steps: Step[]; runId: string }) {
  const roots = buildTree(steps);
  const [openSet, setOpenSet] = useState<Set<string>>(new Set([steps[0]?.step_id].filter(Boolean) as string[]));
  const toggle = (id: string) =>
    setOpenSet((p) => {
      const n = new Set(p);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const maxCost = Math.max(1e-9, ...steps.map((s) => s.cost_usd ?? 0));
  
  return (
    <div className="space-y-0.5">
      {roots.map((n) => (
        <div key={n.step.step_id}>
          <StepRow node={n} depth={0} open={openSet.has(n.step.step_id)} onOpen={() => toggle(n.step.step_id)} runId={runId} maxCost={maxCost} />
        </div>
      ))}
    </div>
  );
}

// --- diff view (compare page) ---------------------------------------------
export function DiffBlock({ a, b }: { a: string; b: string }) {
  const parts = diffWords(a, b);
  return (
    <div className="code-scroll max-h-96 overflow-auto rounded-xl border border-neutral-800 bg-neutral-950 p-4 text-[13px] leading-relaxed">
      {renderDiff(parts)}
    </div>
  );
}

function renderDiff(parts: DiffPart[]) {
  return parts.map((p, i) =>
    p.type === "same" ? (
      <span key={i}>{p.text}</span>
    ) : p.type === "add" ? (
      <span key={i} className="diff-add">{p.text}</span>
    ) : (
      <span key={i} className="diff-del">{p.text}</span>
    )
  );
}
