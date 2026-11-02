"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { listRuns, fmtMs, fmtUsd, type RunSummary } from "@/lib/api";

interface DocLink {
  slug: string;
  title: string;
  summary: string;
  order: number;
}

const STEPS = [
  { t: "Plan", d: "The planner breaks the task into three to five sub-tasks with explicit dependencies." },
  { t: "Tool call", d: "A sub-task runs against a sandboxed tool: fetch, query, search or code execution." },
  { t: "LLM call", d: "Pure reasoning steps run against the configured provider with no tool attached." },
  { t: "Critique", d: "The critic reads the scratchpad and the draft output, then passes or asks for revision." },
];

const CONCEPTS = [
  { t: "Traces", d: "Every agent run is recorded: plans, tool calls, LLM outputs, revisions, and critiques. Traces are committed, diffable artifacts." },
  { t: "Evaluation", d: "Deterministic scorers and LLM judges measure task correctness, token efficiency, and latency. Compare configs across runs." },
  { t: "Sandbox", d: "Tool execution runs in ephemeral Docker containers with network isolation, read-only filesystems, and strict resource limits." },
  { t: "Critic loop", d: "Agents critique their own outputs, revise on failures, and converge within a bounded loop. Force-pass on the final iteration." },
  { t: "Reports", d: "Static HTML reports embed charts, traces, and eval results. No live dashboard. Reproducible, diff-friendly, offline-ready." },
  { t: "Architecture", d: "Planner, executor, critic. Composable orchestrator with pluggable tools, LLM providers, scorers, and storage backends." },
];

const PRINCIPLES = [
  { t: "Deterministic", d: "Outputs reproduce exactly, so an evaluation run means the same thing twice." },
  { t: "Bounded", d: "Every loop has a ceiling; the critic force-passes on the final iteration." },
  { t: "Static", d: "Reports are files, not a server: diff-friendly, auditable, offline-ready." },
  { t: "Isolated", d: "Tool execution never touches the host: no network, read-only disk, a resource cap." },
  { t: "Separated", d: "Orchestration and infrastructure stay apart, so either can change alone." },
];

export default function HomePage({ docs }: { docs: DocLink[] }) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listRuns(50).then(setRuns).catch((e) => setErr(String(e)));
  }, []);

  const latestRun = useMemo(() => runs[0], [runs]);

  return (
    <>
      <section className="hero">
        <div className="container hero__grid">
          <div className="hero__text">
            <h1>Multi-agent orchestration, drawn in the open</h1>
            <p className="lead">
              Agent Forge plans, runs and critiques multi-agent tasks in sandboxed steps, and records every one as a trace you can read.
            </p>
            <div className="hero__actions">
              <Link href="/traces" className="btn">
                View traces
              </Link>
              <Link href="/docs/getting-started" className="btn btn--quiet">
                Getting started
              </Link>
            </div>
          </div>

          <figure className="elev">
            <div className="elev__sheet">
              <ol className="elev__track">
                {STEPS.map((s, i) => (
                  <li key={s.t} className={`elev__node${i === 2 ? " elev__node--key" : ""}`}>
                    <span className="elev__t">{s.t}</span>
                    <span className="elev__d">{s.d}</span>
                  </li>
                ))}
              </ol>
              <div className="elev__loop">
                <span className="elev__t">Revision</span>
                <span className="elev__d">loops back to tool call or LLM call until the critic passes, or the step ceiling is reached.</span>
              </div>
            </div>
            <figcaption className="elev__caption">The five step types a run is built from, drawn in the order a plan executes them.</figcaption>
          </figure>
        </div>
      </section>

      <section className="plate">
        <div className="container">
          <div className="plate__head">
            <h2>Core concepts</h2>
          </div>
          <div className="register">
            {CONCEPTS.map((c, i) => (
              <div className="register__row" key={c.t}>
                <span className="register__n">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="register__t">{c.t}</h3>
                <p className="register__p">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {latestRun && (
        <section className="plate plate--band">
          <div className="container">
            <div className="plate__head">
              <h2>Latest trace</h2>
            </div>
            <div className="latest">
              <div>
                <p className="latest__task">{latestRun.task}</p>
                <div className="latest__acts">
                  <Link href={`/traces/${latestRun.run_id}`} className="link-rule">
                    Inspect run
                  </Link>
                </div>
              </div>
              <div className="gauge">
                <div className="gauge__item">
                  <span className="gauge__v">{fmtMs(latestRun.duration_ms)}</span>
                  <span className="gauge__l">Duration</span>
                </div>
                <div className="gauge__item">
                  <span className="gauge__v">{fmtUsd(latestRun.cost_usd)}</span>
                  <span className="gauge__l">Cost</span>
                </div>
                <div className="gauge__item">
                  <span className="gauge__v">{latestRun.n_steps}</span>
                  <span className="gauge__l">Steps</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="plate">
        <div className="container">
          <div className="plate__head">
            <h2>Design philosophy</h2>
          </div>
          <div className="principle">
            {PRINCIPLES.map((p) => (
              <div className="principle__item" key={p.t}>
                <span className="principle__t">{p.t}</span>
                <span className="principle__d">{p.d}</span>
              </div>
            ))}
          </div>
          <div className="philosophy__more">
            <p className="philosophy__statement">A clear separation between orchestration and infrastructure, so either can be rebuilt without the other.</p>
            <Link href="/docs/design-decisions" className="link-rule">
              Read the ADRs
            </Link>
          </div>
        </div>
      </section>

      {docs.length > 0 && (
        <section className="plate">
          <div className="container">
            <div className="plate__head">
              <h2>Documentation</h2>
            </div>
            <div className="register">
              {docs.map((doc, i) => (
                <div className="register__row" key={doc.slug}>
                  <span className="register__n">{String(i + 1).padStart(2, "0")}</span>
                  <h3 className="register__t">
                    <Link href={`/docs/${doc.slug}`} className="register__link">
                      {doc.title}
                    </Link>
                  </h3>
                  <p className="register__p">{doc.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="plate">
        <div className="container">
          <div className="plate__head">
            <h2>Recent runs</h2>
          </div>
          {err && <p className="reg__err">API unreachable. View traces manually.</p>}
          {runs.length > 0 ? (
            <table className="reg">
              <thead>
                <tr>
                  <th>Task</th>
                  <th className="reg__hide">Duration</th>
                  <th className="reg__hide">Cost</th>
                  <th>Steps</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 5).map((r) => (
                  <tr key={r.run_id}>
                    <td>
                      <Link href={`/traces/${r.run_id}`} className="reg__task">
                        {r.task.slice(0, 60)}
                      </Link>
                    </td>
                    <td className="reg__hide">
                      <span className="reg__num">{fmtMs(r.duration_ms)}</span>
                    </td>
                    <td className="reg__hide">
                      <span className="reg__num">{fmtUsd(r.cost_usd)}</span>
                    </td>
                    <td>
                      <span className="reg__num">{r.n_steps}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="reg__empty">No traces yet. POST a task to the API to create one.</p>
          )}
        </div>
      </section>
    </>
  );
}
