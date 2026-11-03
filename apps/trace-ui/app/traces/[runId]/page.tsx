import { readFileSync } from "fs";
import { join } from "path";
import Link from "next/link";

interface Step {
  step_id: number;
  type: string;
  tool_name?: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  tokens: { in: number; out: number };
  latency_ms: number;
  cost_usd: number;
  parent_step_id?: number;
  artifacts?: Array<{ name: string; mime: string; data_base64?: string }>;
}

interface Trace {
  run_id: string;
  task: string;
  steps: Step[];
  status: string;
  final_output: Record<string, unknown>;
  timestamp: string;
}

function loadTrace(runId: string): Trace | null {
  try {
    const tracesDir = join(process.cwd(), "reports", "traces");
    const file = join(tracesDir, `${runId}.json`);
    const content = readFileSync(file, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function formatCost(usd: number) {
  return `$${usd.toFixed(4)}`;
}

function formatLatency(ms: number) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function typeTone(type: string) {
  if (type === "critique" || type === "revision") return "chip--amber";
  if (type === "plan" || type === "tool_call" || type === "llm_call" || type === "code_exec") return "chip--cool";
  return "chip--muted";
}

function statusTone(status: string) {
  if (status === "succeeded") return "chip--ok";
  if (status === "failed") return "chip--bad";
  if (status === "running") return "chip--amber";
  return "chip--muted";
}

function StepBadge({ type }: { type: string }) {
  return <span className={`chip ${typeTone(type)}`}>{type.replace(/_/g, " ")}</span>;
}

export default async function TraceDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const trace = loadTrace(runId);

  if (!trace) {
    return (
      <div className="shell page">
        <div className="empty">
          <h1 className="empty__title">Trace not found</h1>
          <p className="empty__line">
            Run ID <span className="empty__path">{runId}</span>
          </p>
          <div className="empty__actions">
            <Link href="/traces" className="btn btn--quiet">
              Back to traces
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const totalCost = trace.steps.reduce((sum, s) => sum + s.cost_usd, 0);
  const totalLatency = trace.steps.reduce((sum, s) => sum + s.latency_ms, 0);
  const totalTokens = trace.steps.reduce((sum, s) => sum + (s.tokens?.in || 0) + (s.tokens?.out || 0), 0);

  const buildStepTree = (parentId?: number) =>
    trace.steps.filter((s) => (s.parent_step_id || undefined) === parentId);

  const renderStep = (step: Step, level = 0) => (
    <div key={step.step_id} className="trail__item">
      <div className="trail__rail" aria-hidden="true">
        <span className={`trail__dot ${typeTone(step.type) === "chip--amber" ? "swatch--amber" : "swatch--cool"}`} />
      </div>
      <div className="trail__body">
        <article className="step">
          <div className="step__head">
            <span className="step__id">#{step.step_id}</span>
            <StepBadge type={step.type} />
            {step.tool_name && <span className="step__name">{step.tool_name}</span>}
          </div>
          <div className="step__body">
            {step.input && Object.keys(step.input).length > 0 && (
              <div className="step__block">
                <div className="step__label">Input</div>
                <pre className="step__pre">{JSON.stringify(step.input, null, 2)}</pre>
              </div>
            )}

            {step.output && Object.keys(step.output).length > 0 && (
              <div className="step__block">
                <div className="step__label">Output</div>
                <pre className="step__pre">{JSON.stringify(step.output, null, 2)}</pre>
              </div>
            )}

            <div className="step__meta">
              <span>
                latency <span className="mono">{formatLatency(step.latency_ms)}</span>
              </span>
              <span>
                cost <span className="mono">{formatCost(step.cost_usd)}</span>
              </span>
              {step.tokens && (
                <span>
                  tokens{" "}
                  <span className="mono">
                    {step.tokens.in} in / {step.tokens.out} out
                  </span>
                </span>
              )}
            </div>

            {step.artifacts && step.artifacts.length > 0 && (
              <div className="step__artifacts">
                <div className="step__label">Artifacts</div>
                {step.artifacts.map((artifact, idx) => (
                  <div key={idx} className="step__artifact">
                    {artifact.data_base64 && artifact.mime.startsWith("image/") ? (
                      <img
                        src={`data:${artifact.mime};base64,${artifact.data_base64}`}
                        alt={artifact.name}
                      />
                    ) : (
                      <span className="step__artifact-name">
                        {artifact.name} ({artifact.mime})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </article>

        {buildStepTree(step.step_id).length > 0 && (
          <div className="trail__children">
            {buildStepTree(step.step_id).map((child) => renderStep(child, level + 1))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="shell page">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">{trace.task}</h1>
          <div className="trace-head__meta">
            <span className="mono">{trace.run_id}</span>
            <span className={`chip ${statusTone(trace.status)}`}>{trace.status}</span>
          </div>
        </div>
        <div className="page-head__actions">
          <Link href="/traces" className="btn btn--quiet">
            Back to traces
          </Link>
        </div>
      </div>

      <div className="metrics trace-metrics">
        <div className="metric">
          <span className="metric__value">{formatLatency(totalLatency)}</span>
          <span className="metric__label">Duration</span>
        </div>
        <div className="metric">
          <span className="metric__value">{formatCost(totalCost)}</span>
          <span className="metric__label">Cost</span>
        </div>
        <div className="metric">
          <span className="metric__value">{trace.steps.length}</span>
          <span className="metric__label">Steps</span>
        </div>
        <div className="metric">
          <span className="metric__value">{totalTokens.toLocaleString()}</span>
          <span className="metric__label">Tokens</span>
        </div>
      </div>

      <section>
        <div className="timeline-head">
          <h2>Timeline</h2>
        </div>
        <div className="trail">{buildStepTree().map((step) => renderStep(step))}</div>
      </section>

      <section className="final-output">
        <div className="timeline-head">
          <h2>Final output</h2>
        </div>
        <div className="panel">
          <div className="panel__body">
            <pre className="step__pre">{JSON.stringify(trace.final_output, null, 2)}</pre>
          </div>
        </div>
      </section>
    </div>
  );
}
