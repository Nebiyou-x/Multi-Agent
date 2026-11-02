"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { use } from "react";
import type { Run } from "@/lib/api";
import { getRun, fmtMs, fmtUsd, fmtTok } from "@/lib/api";
import { Card, SectionLabel, StatusPill, ModelChip, Delta } from "@/components/ui";
import { DiffBlock } from "@/components/Timeline";

export default function ComparePage({ params }: { params: Promise<{ a: string; b: string }> }) {
  // params must be consumed inside <Suspense> (cacheComponents / PPR).
  return (
    <Suspense fallback={<div className="flex-1 p-10 text-sm text-neutral-500">Loading runs…</div>}>
      <CompareInner params={params} />
    </Suspense>
  );
}

function CompareInner({ params }: { params: Promise<{ a: string; b: string }> }) {
  const { a, b } = use(params);
  const [ra, setRa] = useState<Run | null>(null);
  const [rb, setRb] = useState<Run | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getRun(a).then(setRa).catch((e) => setErr(String(e)));
    getRun(b).then(setRb).catch((e) => setErr(String(e)));
  }, [a, b]);

  if (err && !ra && !rb)
    return (
      <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 text-sm text-red-400">{err}</div>
    );
  if (!ra || !rb)
    return (
      <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 text-sm text-neutral-500">Loading runs…</div>
    );

  const stats = (r: Run) => ({
    cost: r.steps.reduce((x, s) => x + (s.cost_usd ?? 0), 0),
    ms: r.steps.reduce((x, s) => x + (s.latency_ms ?? 0), 0),
    tok: r.steps.reduce((x, s) => x + ((s.tokens?.in ?? 0) + (s.tokens?.out ?? 0)), 0),
    n: r.steps.length,
  });
  const A = stats(ra);
  const B = stats(rb);
  const answer = (r: Run) => String(r.final_output?.answer ?? "");

  const metrics: [string, string, string, number, number][] = [
    ["steps", String(A.n), String(B.n), A.n, B.n],
    ["duration", fmtMs(A.ms), fmtMs(B.ms), A.ms, B.ms],
    ["tokens", fmtTok(A.tok), fmtTok(B.tok), A.tok, B.tok],
    ["cost", fmtUsd(A.cost), fmtUsd(B.cost), A.cost, B.cost],
  ];

  return (
    <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
      <div className="mb-5">
        <Link href="/" className="font-mono text-xs text-neutral-500 hover:text-neutral-300">
          ← all runs
        </Link>
        <div className="mt-3 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Compare runs</h1>
            <p className="mt-1 max-w-2xl text-sm text-neutral-500">{ra.task}</p>
          </div>
          {ra.task !== rb.task && (
            <span className="mt-1 rounded-md bg-amber-500/10 px-2 py-1 font-mono text-[10px] text-amber-300">
              ⚠ different tasks
            </span>
          )}
        </div>
      </div>

      {/* two run cards */}
      <div className="grid grid-cols-2 gap-4">
        {[{ r: ra, id: a, tag: "A" }, { r: rb, id: b, tag: "B" }].map(({ r, id, tag }) => (
          <Card key={tag} glow={tag === "A"} className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[11px] text-neutral-500">
                run <span className="text-neutral-200">{tag}</span> · {r.run_id.slice(0, 8)}
              </span>
              <Link href={`/runs/${id}`} className="font-mono text-[11px] text-indigo-400 hover:underline">
                open →
              </Link>
            </div>
            <div className="mb-3 flex items-center gap-2">
              <ModelChip provider={r.provider} model={r.model} />
              <StatusPill status={r.status} />
            </div>
            <div className="rounded-lg bg-neutral-950 p-3 text-[13px] leading-relaxed text-neutral-300">
              {answer(r) || <span className="text-neutral-600">no answer</span>}
            </div>
          </Card>
        ))}
      </div>

      {/* metrics */}
      <div className="mt-8">
        <SectionLabel>metrics · A vs B</SectionLabel>
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60 text-[10px] uppercase tracking-[0.14em] text-neutral-500">
                <th className="px-4 py-2.5 text-left">metric</th>
                <th className="px-4 py-2.5 text-right">A</th>
                <th className="px-4 py-2.5 text-right">B</th>
                <th className="px-4 py-2.5 text-right">Δ (B vs A)</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, va, vb, xa, xb]) => (
                <tr key={label} className="border-t border-neutral-900 first:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-neutral-500">{label}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums text-neutral-200">{va}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums text-neutral-200">{vb}</td>
                  <td className="px-4 py-2.5 text-right">
                    <Delta from={xa} to={xb} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-right font-mono text-[10px] text-neutral-600">
          green = B is cheaper/faster · amber = B is more expensive
        </p>
      </div>

      {/* answer diff */}
      <div className="mt-8">
        <SectionLabel>answer diff · word-level</SectionLabel>
        <DiffBlock a={answer(ra)} b={answer(rb)} />
      </div>
    </div>
  );
}
