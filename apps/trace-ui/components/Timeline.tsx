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
    <div className="kv__row">
      <span className="kv__k">{k}</span>
      <span className="kv__v">{v}</span>
    </div>
  );
}

function MetaBlock({ step }: { step: Step }) {
  const t = step.tokens ?? { in: 0, out: 0 };
  return (
    <div className="kv">
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
      <div className="step-block">
        <div className="step-panel" style={{ display: "flex", alignItems: "center", gap: "var(--space-xs)" }}>
          <span className={`chip ${v.verdict === "PASS" ? "chip--ok" : "chip--bad"}`}>{v.verdict ?? "n/a"}</span>
          {typeof v.score === "number" && (
            <span className="step-block__label">
              confidence <span className="mono">{(v.score * 100).toFixed(0)}%</span>
            </span>
          )}
        </div>
        {v.feedback && <p className="answer__body">{v.feedback}</p>}
      </div>
    );
  }
  if (step.type === "revision" && typeof out.revised === "string")
    return <p className="answer__body">{out.revised}</p>;

  const artifacts = (Array.isArray(to.artifacts) ? to.artifacts : []) as {
    name: string;
    size: number;
    truncated?: boolean;
  }[];

  if (artifacts.length > 0)
    return (
      <div className="artifact-grid">
        {artifacts.map((a) => (
          <a
            key={a.name}
            href={`${API}/artifacts/${runId}/${a.name}`}
            target="_blank"
            rel="noreferrer"
            className="artifact"
          >
            {isImage(a.name) ? (
              <img src={`${API}/artifacts/${runId}/${a.name}`} alt={a.name} className="artifact__image" />
            ) : (
              <div className="artifact__file">{a.name.split(".").pop()?.toUpperCase()}</div>
            )}
            <div className="artifact__meta">
              <span className="artifact__name">{a.name}</span>
              <span className="artifact__size">
                {a.truncated ? "truncated" : `${(a.size / 1024).toFixed(1)} KB`}
              </span>
            </div>
          </a>
        ))}
      </div>
    );

  if (typeof out.result === "string") return <p className="answer__body">{out.result}</p>;

  return (
    <pre className="step-pre">{highlight(JSON.stringify(step.output ?? {}, null, 2), "json")}</pre>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`step-row__chevron${open ? " step-row__chevron--open" : ""}`}
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3.5 2L7 5L3.5 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
    <div className="step-row">
      <button type="button" onClick={onOpen} className="step-row__toggle" aria-expanded={open}>
        <span className="step-row__swatch">
          <span className={`swatch ${color.swatch}`} aria-hidden="true" />
        </span>
        <span className="step-row__name">{s.name}</span>
        <span className={`chip ${color.chip} step-row__type`}>{s.type.replace("_call", "")}</span>
        {s.error && <span className="chip chip--bad step-row__error">error</span>}
        <span className="step-row__right">
          <span className="step-row__bar">
            <Bar value={s.cost_usd ?? 0} max={maxCost} tone={color.bar} />
          </span>
          <span className="step-row__cost">{fmtUsd(s.cost_usd ?? 0)}</span>
          <span className="step-row__latency">{fmtMs(s.latency_ms ?? 0)}</span>
          <Chevron open={open} />
        </span>
      </button>

      {open && (
        <div className="step-row__panel">
          <div className="tabs">
            {(["output", "input", "meta"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className="tab"
                aria-pressed={tab === t}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="step-panel">
            {tab === "meta" && <MetaBlock step={s} />}

            {tab === "input" && (
              <>
                {codeSrc && (
                  <div className="step-block">
                    <div className="step-block__label">generated code</div>
                    <pre className="step-pre">{highlight(codeSrc, "python")}</pre>
                  </div>
                )}
                {sqlSrc && (
                  <div className="step-block">
                    <div className="step-block__label">sql</div>
                    <pre className="step-pre">{highlight(sqlSrc, "sql")}</pre>
                  </div>
                )}
                {!codeSrc && !sqlSrc && (
                  <pre className="step-pre">{highlight(JSON.stringify(s.input ?? {}, null, 2), "json")}</pre>
                )}
              </>
            )}

            {tab === "output" && <OutputView step={s} runId={runId} />}
          </div>

          {s.error && (
            <div className="step-error">
              <div className="step-error__label">error</div>
              <p className="step-error__text">{s.error}</p>
            </div>
          )}
        </div>
      )}

      {open && node.children.length > 0 && (
        <div className="trail__children">
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
  return (
    <StepRow
      node={node}
      depth={depth}
      open={open}
      onOpen={() => setOpen((o) => !o)}
      runId={runId}
      maxCost={maxCost}
    />
  );
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
    <div className="timeline">
      {roots.map((n) => (
        <StepRow
          key={n.step.step_id}
          node={n}
          depth={0}
          open={openSet.has(n.step.step_id)}
          onOpen={() => toggle(n.step.step_id)}
          runId={runId}
          maxCost={maxCost}
        />
      ))}
    </div>
  );
}

// --- diff view (compare page) ---------------------------------------------
export function DiffBlock({ a, b }: { a: string; b: string }) {
  const parts = diffWords(a, b);
  return <div className="diff">{renderDiff(parts)}</div>;
}

function renderDiff(parts: DiffPart[]) {
  return parts.map((p, i) =>
    p.type === "same" ? (
      <span key={i}>{p.text}</span>
    ) : p.type === "add" ? (
      <span key={i} className="diff-add">
        {p.text}
      </span>
    ) : (
      <span key={i} className="diff-del">
        {p.text}
      </span>
    )
  );
}
