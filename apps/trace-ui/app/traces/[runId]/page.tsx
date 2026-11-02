import { readFileSync } from "fs";
import { join } from "path";
import Link from "next/link";

interface Step {
  step_id: number;
  type: string;
  tool_name?: string;
  input: Record<string, any>;
  output: Record<string, any>;
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
  final_output: Record<string, any>;
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

function StepBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    plan: "bg-blue-600/20 text-blue-300",
    tool_call: "bg-purple-600/20 text-purple-300",
    llm_call: "bg-indigo-600/20 text-indigo-300",
    code_exec: "bg-green-600/20 text-green-300",
    critique: "bg-orange-600/20 text-orange-300",
    revision: "bg-yellow-600/20 text-yellow-300",
  };
  return (
    <span className={`inline-block px-2 py-1 text-xs font-medium rounded ${colors[type] || "bg-neutral-700/40 text-neutral-400"}`}>
      {type.replace(/_/g, " ")}
    </span>
  );
}

export default function TraceDetailPage({ params }: { params: { runId: string } }) {
  const trace = loadTrace(params.runId);

  if (!trace) {
    return (
      <div className="mx-auto w-full max-w-7xl px-6 py-10">
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold mb-2">Trace not found</h1>
          <p className="text-neutral-400 mb-6">Run ID: {params.runId}</p>
          <Link href="/traces" className="text-indigo-400 hover:text-indigo-300">
            ← Back to traces
          </Link>
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
    <div key={step.step_id} className="mb-4">
      <div className="flex items-start gap-4 p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
        <div className="flex-shrink-0">
          <StepBadge type={step.type} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-xs text-neutral-500">#{step.step_id}</span>
            {step.tool_name && <span className="font-mono text-xs text-indigo-400">{step.tool_name}</span>}
          </div>

          {step.input && Object.keys(step.input).length > 0 && (
            <div className="mb-3 text-sm">
              <div className="text-xs text-neutral-500 mb-1">Input:</div>
              <pre className="bg-neutral-900/50 p-2 rounded text-xs overflow-x-auto text-neutral-300">
                {JSON.stringify(step.input, null, 2)}
              </pre>
            </div>
          )}

          {step.output && Object.keys(step.output).length > 0 && (
            <div className="mb-3 text-sm">
              <div className="text-xs text-neutral-500 mb-1">Output:</div>
              <pre className="bg-neutral-900/50 p-2 rounded text-xs overflow-x-auto text-neutral-300">
                {JSON.stringify(step.output, null, 2)}
              </pre>
            </div>
          )}

          <div className="flex gap-6 text-xs text-neutral-500 font-mono">
            <span>⏱ {formatLatency(step.latency_ms)}</span>
            <span>💰 {formatCost(step.cost_usd)}</span>
            {step.tokens && <span>📝 {step.tokens.in} in · {step.tokens.out} out</span>}
          </div>

          {step.artifacts && step.artifacts.length > 0 && (
            <div className="mt-3 text-sm">
              <div className="text-xs text-neutral-500 mb-2">Artifacts:</div>
              <div className="space-y-2">
                {step.artifacts.map((artifact, idx) => (
                  <div key={idx} className="text-xs">
                    {artifact.data_base64 && artifact.mime.startsWith("image/") ? (
                      <img
                        src={`data:${artifact.mime};base64,${artifact.data_base64}`}
                        alt={artifact.name}
                        className="max-w-sm rounded border border-neutral-700"
                      />
                    ) : (
                      <span className="text-neutral-500">{artifact.name} ({artifact.mime})</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {buildStepTree(step.step_id).length > 0 && (
        <div className="ml-6 border-l border-neutral-800 pl-4 mt-2 mb-4">
          {buildStepTree(step.step_id).map((child) => renderStep(child, level + 1))}
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-10">
      <Link href="/traces" className="mb-6 text-indigo-400 hover:text-indigo-300 text-sm">
        ← Back to traces
      </Link>

      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{trace.task}</h1>
        <div className="flex flex-wrap gap-4 text-sm text-neutral-400">
          <span className="font-mono">{trace.run_id}</span>
          <span>Status: {trace.status}</span>
        </div>
      </div>

      <div className="grid gap-4 grid-cols-2 sm:grid-cols-4 mb-8">
        <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
          <div className="text-xs text-neutral-500 mb-1">Duration</div>
          <div className="font-mono text-lg">{formatLatency(totalLatency)}</div>
        </div>
        <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
          <div className="text-xs text-neutral-500 mb-1">Cost</div>
          <div className="font-mono text-lg">{formatCost(totalCost)}</div>
        </div>
        <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
          <div className="text-xs text-neutral-500 mb-1">Steps</div>
          <div className="font-mono text-lg">{trace.steps.length}</div>
        </div>
        <div className="p-4 rounded-lg border border-neutral-800 bg-neutral-950/40">
          <div className="text-xs text-neutral-500 mb-1">Tokens</div>
          <div className="font-mono text-lg">{totalTokens.toLocaleString()}</div>
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-bold mb-4">Timeline</h2>
        <div>{buildStepTree().map((step) => renderStep(step))}</div>
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-bold mb-4">Final output</h2>
        <pre className="bg-neutral-900/50 p-4 rounded text-sm overflow-x-auto text-neutral-300">
          {JSON.stringify(trace.final_output, null, 2)}
        </pre>
      </div>
    </div>
  );
}
