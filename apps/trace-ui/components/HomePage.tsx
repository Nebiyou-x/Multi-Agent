import Link from "next/link";
import { StatusPill } from "@/components/ui";
import type { TraceSummary } from "@/lib/traces";

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

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

function fmtUsd(value: number): string {
  return value === 0 ? "$0.00" : `$${value.toFixed(4)}`;
}

export default function HomePage({
  docs,
  traces,
}: {
  docs: DocLink[];
  traces: TraceSummary[];
}) {
  const latestTrace = traces[0];

  return (
    <div className="shell page workbench">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Workbench</h1>
          <p className="page-head__line">
            Agent Forge plans, runs and critiques multi-agent tasks in sandboxed steps, and records every one as a trace you can read.
          </p>
          <p className="page-head__meta">Committed trace reports</p>
        </div>
        <div className="page-head__actions">
          <Link href="/traces" className="btn btn--primary">
            Open traces
          </Link>
          <Link href="/docs/getting-started" className="btn btn--quiet">
            Getting started
          </Link>
        </div>
      </div>

      <div className="workbench__grid">
        <div className="workbench__main">
          {latestTrace && (
            <article className="panel panel--lead">
              <div className="panel__head">
                <h2 className="panel__title">Latest committed trace</h2>
                <StatusPill status={latestTrace.status} />
              </div>
              <div className="panel__body record">
                <p className="record__task">{latestTrace.task}</p>
                <div className="record__meta">
                  <div className="meta__item">
                    <span className="meta__label">Trace</span>
                    <span className="meta__value">{latestTrace.runId.slice(0, 8)}</span>
                  </div>
                  <div className="meta__item">
                    <span className="meta__label">Recorded</span>
                    <span className="meta__value">{latestTrace.timestamp.slice(0, 10)}</span>
                  </div>
                </div>
                <div className="metrics metrics--three">
                  <div className="metric">
                    <span className="metric__value">{fmtMs(latestTrace.durationMs)}</span>
                    <span className="metric__label">Duration</span>
                  </div>
                  <div className="metric">
                    <span className="metric__value">{fmtUsd(latestTrace.costUsd)}</span>
                    <span className="metric__label">Cost</span>
                  </div>
                  <div className="metric">
                    <span className="metric__value">{latestTrace.stepCount}</span>
                    <span className="metric__label">Steps</span>
                  </div>
                </div>
                <div className="record__actions">
                  <Link href={`/traces/${latestTrace.runId}`} className="btn btn--primary">
                    Inspect trace
                  </Link>
                  <Link href="/traces" className="btn btn--quiet">
                    All traces
                  </Link>
                </div>
              </div>
            </article>
          )}

          {!latestTrace && (
            <div className="panel">
              <div className="panel__head">
                <h2 className="panel__title">Latest committed trace</h2>
              </div>
              <div className="panel__body">
                <div className="empty">
                  <h3 className="empty__title">No committed traces yet</h3>
                  <p className="empty__line">
                    Committed trace reports will appear here when available.
                  </p>
                  <div className="empty__actions">
                    <Link href="/docs/running-a-task" className="btn btn--primary">
                      Read how to run a task
                    </Link>
                    <Link href="/traces" className="btn btn--quiet">
                      Open committed traces
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}

          <section>
            <div className="timeline-head">
              <h2>Recent traces</h2>
              <Link href="/traces" className="table__action">
                All traces
              </Link>
            </div>
            {traces.length > 0 && (
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Task</th>
                      <th>Trace</th>
                      <th className="hide-sm">Duration</th>
                      <th className="hide-sm">Cost</th>
                      <th>Steps</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traces.slice(0, 5).map((trace) => (
                      <tr key={trace.runId}>
                        <td>
                          <Link href={`/traces/${trace.runId}`} className="table__task">
                            {trace.task.slice(0, 60)}
                          </Link>
                        </td>
                        <td>
                          <Link href={`/traces/${trace.runId}`} className="table__action">
                            {trace.runId.slice(0, 8)}
                          </Link>
                        </td>
                        <td className="hide-sm">
                          <span className="table__num">{fmtMs(trace.durationMs)}</span>
                        </td>
                        <td className="hide-sm">
                          <span className="table__num">{fmtUsd(trace.costUsd)}</span>
                        </td>
                        <td>
                          <span className="table__num">{trace.stepCount}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {traces.length === 0 && <p className="empty__line">No committed traces yet.</p>}
          </section>

          <section>
            <div className="timeline-head">
              <h2>Documentation</h2>
              <Link href="/docs" className="table__action">
                All docs
              </Link>
            </div>
            {docs.length > 0 ? (
              <ul className="docs-list">
                {docs.map((doc) => (
                  <li className="docs-list__item" key={doc.slug}>
                    <h3>
                      <Link href={`/docs/${doc.slug}`} className="docs-list__title">
                        {doc.title}
                      </Link>
                    </h3>
                    <p className="docs-list__summary">{doc.summary}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty__line">No documentation files were found.</p>
            )}
          </section>
        </div>

        <aside className="workbench__side">
          <section className="panel">
            <div className="panel__head">
              <h2 className="panel__title">The run loop</h2>
            </div>
            <div className="panel__body runloop">
              <ol className="runloop__list">
                {STEPS.map((step, index) => (
                  <li className={`runloop__item${index >= 3 ? " runloop__item--amber" : ""}`} key={step.t}>
                    <span className="runloop__n">{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <div className="runloop__name">{step.t}</div>
                      <p className="runloop__desc">{step.d}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="runloop__loop">
                <span className="runloop__name">Revision</span>
                <p className="runloop__desc">
                  loops back to tool call or LLM call until the critic passes, or the step ceiling is reached.
                </p>
              </div>
              <p className="runloop__caption">The five step types a run is built from, drawn in the order a plan executes them.</p>
            </div>
          </section>
        </aside>
      </div>

      <section>
        <div className="reference">
          <div className="reference__group">
            <div className="timeline-head">
              <h2>Core concepts</h2>
            </div>
            <div className="reference__list">
              {CONCEPTS.map((concept) => (
                <div className="reference__item" key={concept.t}>
                  <h3 className="reference__term">{concept.t}</h3>
                  <p className="reference__desc">{concept.d}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="reference__group">
            <div className="timeline-head">
              <h2>Design philosophy</h2>
            </div>
            <div className="reference__list">
              {PRINCIPLES.map((principle) => (
                <div className="reference__item" key={principle.t}>
                  <h3 className="reference__term">{principle.t}</h3>
                  <p className="reference__desc">{principle.d}</p>
                </div>
              ))}
            </div>
            <div className="statement">
              <p className="statement__line">
                A clear separation between orchestration and infrastructure, so either can be rebuilt without the other.
              </p>
              <div className="statement__actions">
                <Link href="/docs/design-decisions" className="btn btn--quiet">
                  Read the ADRs
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
