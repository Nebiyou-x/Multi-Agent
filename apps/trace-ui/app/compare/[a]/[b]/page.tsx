"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { use } from "react";
import type { Run } from "@/lib/api";
import { getRun, fmtMs, fmtUsd, fmtTok } from "@/lib/api";
import { SectionLabel, StatusPill, ModelChip, Delta } from "@/components/ui";
import { DiffBlock } from "@/components/Timeline";

export default function ComparePage({ params }: { params: Promise<{ a: string; b: string }> }) {
  // params must be consumed inside <Suspense> (cacheComponents / PPR).
  return (
    <Suspense
      fallback={
        <div className="shell page">
          <p className="empty__line">Loading runs</p>
        </div>
      }
    >
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
      <div className="shell page">
        <div className="empty">
          <h1 className="empty__title">The runs could not be read</h1>
          <p className="empty__line">{err}</p>
          <div className="empty__actions">
            <Link href="/" className="btn btn--quiet">
              Back to all runs
            </Link>
          </div>
        </div>
      </div>
    );
  if (!ra || !rb)
    return (
      <div className="shell page">
        <p className="empty__line">Loading runs</p>
      </div>
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
    ["Steps", String(A.n), String(B.n), A.n, B.n],
    ["Duration", fmtMs(A.ms), fmtMs(B.ms), A.ms, B.ms],
    ["Tokens", fmtTok(A.tok), fmtTok(B.tok), A.tok, B.tok],
    ["Cost", fmtUsd(A.cost), fmtUsd(B.cost), A.cost, B.cost],
  ];

  return (
    <div className="shell page">
      <div className="page-head">
        <div>
          <Link href="/" className="link link--quiet">
            All runs
          </Link>
          <h1 className="page-head__title" style={{ marginTop: "var(--space-xs)" }}>
            Compare runs
          </h1>
          <p className="page-head__line">{ra.task}</p>
        </div>
        <div className="page-head__actions">
          {ra.task !== rb.task && <span className="chip chip--amber">Different tasks</span>}
        </div>
      </div>

      <div className="compare-grid">
        {[{ r: ra, id: a, tag: "A" }, { r: rb, id: b, tag: "B" }].map(({ r, id, tag }) => (
          <div key={tag} className={`panel${tag === "A" ? " panel--lead" : ""}`}>
            <div className="panel__body compare-card">
              <div className="compare-card__top">
                <span className="compare-card__id">
                  run <b>{tag}</b> {r.run_id.slice(0, 8)}
                </span>
                <Link href={`/runs/${id}`} className="table__action">
                  Open run
                </Link>
              </div>
              <div className="compare-card__chips">
                <ModelChip provider={r.provider} model={r.model} />
                <StatusPill status={r.status} />
              </div>
              <div className="compare-card__answer">
                {answer(r) || <span className="compare-card__empty">no answer</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      <section className="final-output">
        <SectionLabel>Metrics, A against B</SectionLabel>
        <div className="table-scroll" style={{ marginTop: "var(--space-sm)" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num-right">A</th>
                <th className="num-right">B</th>
                <th className="num-right">Change, B vs A</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, va, vb, xa, xb]) => (
                <tr key={label}>
                  <td>
                    <span className="table__id">{label}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{va}</span>
                  </td>
                  <td className="num-right">
                    <span className="table__num">{vb}</span>
                  </td>
                  <td className="num-right">
                    <Delta from={xa} to={xb} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="delta-legend">Green means B is cheaper or faster. Red means B is more expensive.</p>
      </section>

      <section className="diff-panel">
        <SectionLabel>Answer diff, word level</SectionLabel>
        <div style={{ marginTop: "var(--space-sm)" }}>
          <DiffBlock a={answer(ra)} b={answer(rb)} />
        </div>
      </section>
    </div>
  );
}
