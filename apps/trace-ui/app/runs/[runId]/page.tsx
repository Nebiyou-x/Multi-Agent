"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { use } from "react";
import type { Run, Config } from "@/lib/api";
import { getRun, getConfig, replayRun, artifactUrl, fmtMs, fmtUsd, fmtTok, breakdownCost } from "@/lib/api";
import { StatusPill, ModelChip, Bar, PhaseLegend } from "@/components/ui";
import Timeline from "@/components/Timeline";

export default function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  // params must be consumed inside <Suspense> - cacheComponents (PPR)
  // prerenders the static shell and streams the dynamic part in.
  return (
    <Suspense
      fallback={
        <div className="shell page">
          <p className="empty__line">Loading run</p>
        </div>
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
      <div className="shell page">
        <div className="empty">
          <h1 className="empty__title">The run could not be read</h1>
          <p className="empty__line">{err}</p>
          <div className="empty__actions">
            <Link href="/" className="btn btn--quiet">
              Back to all runs
            </Link>
          </div>
        </div>
      </div>
    );
  if (!run)
    return (
      <div className="shell page">
        <p className="empty__line">Loading run</p>
      </div>
    );

  const artifacts: string[] = run.final_output?.artifacts ?? [];
  const breakdown = breakdownCost(run.steps);
  const totalMs = run.steps.reduce((a, s) => a + (s.latency_ms ?? 0), 0);
  const totalTok = run.steps.reduce((a, s) => a + ((s.tokens?.in ?? 0) + (s.tokens?.out ?? 0)), 0);

  return (
    <div className="shell page">
      <div className="run-head">
        <div className="run-head__top">
          <Link href="/" className="link link--quiet">
            All runs
          </Link>
          <div className="run-head__actions">
            <ModelChip provider={run.provider} model={run.model} />
            <StatusPill status={run.status} />
          </div>
        </div>
        <h1>{run.task}</h1>
        <div className="run-meta">
          <span className="mono">{run.run_id.slice(0, 8)}</span>
          <span>{new Date(run.created_at).toLocaleString()}</span>
        </div>
      </div>

      <div className="metrics run-metrics">
        {[
          ["Total cost", fmtUsd(breakdown.total)],
          ["Duration", fmtMs(totalMs)],
          ["Tokens", fmtTok(totalTok)],
          ["Steps", String(run.steps.length)],
        ].map(([label, value]) => (
          <div key={label} className="metric">
            <span className="metric__value">{value}</span>
            <span className="metric__label">{label}</span>
          </div>
        ))}
      </div>

      {run.final_output?.answer && (
        <section className="answer">
          <div className="panel panel--lead">
            <div className="panel__head">
              <h2 className="panel__title">Final answer</h2>
            </div>
            <div className="panel__body">
              <p className="answer__body">{run.final_output.answer}</p>
              {artifacts.length > 0 && (
                <div className="artifacts">
                  {artifacts.map((a) => (
                    <a
                      key={a}
                      href={artifactUrl(a)}
                      target="_blank"
                      rel="noreferrer"
                      className="artifact-link"
                    >
                      {a.split("/").pop()}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="replay">
        <div className="panel">
          <div className="panel__head">
            <h2 className="panel__title">Replay</h2>
          </div>
          <div className="panel__body">
            <div className="replay__row">
              <div className="field">
                <label className="field__label" htmlFor="replay-provider">
                  Provider
                </label>
                <select
                  id="replay-provider"
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value);
                    setModel("");
                  }}
                  className="select"
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
              </div>
              <div className="field">
                <label className="field__label" htmlFor="replay-model">
                  Model
                </label>
                <select
                  id="replay-model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={!provider}
                  className="select"
                >
                  <option value="">default model</option>
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <button type="button" onClick={doReplay} disabled={replaying} className="btn btn--primary">
                {replaying ? "Running" : "Replay"}
              </button>
            </div>
            {newRunId && (
              <div className="replay__result">
                <span className="chip chip--ok">Run started</span>
                <Link href={`/runs/${newRunId}`} className="link">
                  Open run {newRunId.slice(0, 8)}
                </Link>
              </div>
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="timeline-head">
          <h2>Cost by phase</h2>
        </div>
        <div className="phase-costs">
          {breakdown.per_type.map((t) => {
            const max = Math.max(...breakdown.per_type.map((x) => x.cost));
            return (
              <div key={t.type} className="phase-cost">
                <div className="phase-cost__top">
                  <span className="phase-cost__name">{t.type.replace("_call", "")}</span>
                  <span className="phase-cost__value">{fmtUsd(t.cost)}</span>
                </div>
                <Bar value={t.cost} max={max || 1e-9} tone="bar-fill--cool" />
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <div className="timeline-head">
          <h2>
            {run.steps.length} steps, {fmtUsd(breakdown.total)}
          </h2>
          <PhaseLegend />
        </div>
        <div className="panel">
          <Timeline steps={run.steps} runId={run.run_id} />
        </div>
      </section>
    </div>
  );
}
