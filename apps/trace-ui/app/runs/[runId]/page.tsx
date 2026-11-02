"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { use } from "react";
import type { Run, Config } from "@/lib/api";
import { getRun, getConfig, replayRun, artifactUrl, fmtMs, fmtUsd, fmtTok, breakdownCost } from "@/lib/api";
import { Card, SectionLabel, StatusPill, ModelChip, Bar, PhaseLegend } from "@/components/ui";
import Timeline from "@/components/Timeline";

export default function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  // params must be consumed inside <Suspense> - cacheComponents (PPR)
  // prerenders the static shell and streams the dynamic part in.
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 text-sm text-neutral-500">Loading run…</div>
      }
    >
      <RunDetailInner params={params} />
    </Suspense>
  );
}

function RunDetailInner({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const [run, setRun] = useState<Run | null>(null);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // replay controls
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [replaying, setReplaying] = useState(false);
  const [newRunId, setNewRunId] = useState<string | null>(null);

  useEffect(() => {
    getRun(runId).then(setRun).catch((e) => setErr(String(e)));
    getConfig().then(setCfg).catch(() => {});
  }, [runId]);

  const models = cfg ? (cfg.providers[provider] ?? []) : [];

  async function doReplay() {
    if (!run) return;
    setReplaying(true);
    setNewRunId(null);
    try {
      const next = await replayRun(run.task, provider || undefined, model || undefined);
      setNewRunId(next.run_id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setReplaying(false);
    }
  }

  if (err && !run)
    return (
      <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 text-sm text-red-400">
        {err}
      </div>
    );
  if (!run)
    return (
      <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-10 text-sm text-neutral-500">Loading run…</div>
    );

  const artifacts: string[] = run.final_output?.artifacts ?? [];
  const breakdown = breakdownCost(run.steps);
  const totalMs = run.steps.reduce((a, s) => a + (s.latency_ms ?? 0), 0);
  const totalTok = run.steps.reduce((a, s) => a + ((s.tokens?.in ?? 0) + (s.tokens?.out ?? 0)), 0);

  return (
    <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
      {/* top row: back + status */}
      <div className="mb-4 flex items-center justify-between">
        <Link href="/" className="font-mono text-xs text-neutral-500 hover:text-neutral-300">
          ← all runs
        </Link>
        <div className="flex items-center gap-2">
          <ModelChip provider={run.provider} model={run.model} />
          <StatusPill status={run.status} />
        </div>
      </div>

      <h1 className="max-w-3xl text-2xl font-semibold leading-tight tracking-tight text-neutral-50">{run.task}</h1>
      <div className="mt-1 font-mono text-[11px] text-neutral-500">
        {run.run_id.slice(0, 8)} · {new Date(run.created_at).toLocaleString()}
      </div>

      {/* metrics strip */}
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["total cost", fmtUsd(breakdown.total)],
          ["duration", fmtMs(totalMs)],
          ["tokens", fmtTok(totalTok)],
          ["steps", String(run.steps.length)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
            <div className="font-mono text-lg tabular-nums">{value}</div>
            <div className="font-mono text-[10px] uppercase tracking-wide text-neutral-600">{label}</div>
          </div>
        ))}
      </div>

      {/* answer + artifacts */}
      {run.final_output?.answer && (
        <Card glow className="mt-6 p-4">
          <SectionLabel>final answer</SectionLabel>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-200">{run.final_output.answer}</p>
          {artifacts.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {artifacts.map((a) => (
                <a
                  key={a}
                  href={artifactUrl(a)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-neutral-800 px-2.5 py-1.5 font-mono text-[11px] text-neutral-400 transition-colors hover:border-neutral-600 hover:text-neutral-200"
                >
                  ↗ {a.split("/").pop()}
                </a>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* replay */}
      <Card className="mt-6 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-neutral-500">
              replay with
            </label>
            <div className="flex gap-2">
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setModel("");
                }}
                className="rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 py-1.5 font-mono text-xs text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">default provider</option>
                {cfg
                  ? Object.entries(cfg.providers).map(([p, ms]) =>
                      cfg.api_keys[p] ? (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ) : null
                    )
                  : null}
              </select>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={!provider}
                className="rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 py-1.5 font-mono text-xs text-neutral-200 disabled:opacity-40 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">default model</option>
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button
            onClick={doReplay}
            disabled={replaying}
            className="rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 px-3.5 py-1.5 font-mono text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-110 disabled:opacity-50"
          >
            {replaying ? "running…" : "replay ↻"}
          </button>
          {newRunId && (
            <Link
              href={`/runs/${newRunId}`}
              className="rounded-lg bg-emerald-600/20 px-3.5 py-1.5 font-mono text-xs text-emerald-300 transition-colors hover:bg-emerald-600/30"
            >
              open new run {newRunId.slice(0, 8)} →
            </Link>
          )}
        </div>
      </Card>

      {/* cost breakdown by phase */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {breakdown.per_type.map((t) => {
          const max = Math.max(...breakdown.per_type.map((x) => x.cost));
          return (
            <div key={t.type} className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
              <div className="mb-1 flex items-center justify-between font-mono text-[10px] text-neutral-500">
                <span className="uppercase">{t.type.replace("_call", "")}</span>
                <span className="tabular-nums text-neutral-400">{fmtUsd(t.cost)}</span>
              </div>
              <Bar value={t.cost} max={max || 1e-9} tone="bg-accent" />
            </div>
          );
        })}
      </div>

      {/* the money shot: vertical timeline of steps */}
      <section className="mt-6">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-neutral-500">
            {run.steps.length} steps · {fmtUsd(breakdown.total)}
          </h2>
          <PhaseLegend />
        </div>
        <Card className="p-2">
          <Timeline steps={run.steps} runId={run.run_id} />
        </Card>
      </section>
    </div>
  );
}
