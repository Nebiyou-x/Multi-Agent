"""Pydantic models for Agent Forge trace + eval JSON.

Frozen contract. These are the two JSON shapes the whole reporting pipeline
trusts: the *trace* (one run through the planner/executor/critic loop) and
the *eval results* (one scoring pass over a golden dataset).

Every loader in this package validates on load and fails loudly:
``load_trace`` / ``load_eval`` raise ``ReportError`` with the offending field
named, so a malformed file never silently becomes a wrong report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ReportError(Exception):
    """Raised when a report input file cannot be parsed or validated."""


def _fail(what: str, err: ValidationError) -> "ReportError":
    """Flatten a pydantic error into one line per problem, keyed by field."""
    lines = [f"{what}: input failed schema validation:"]
    for p in err.errors():
        loc = ".".join(str(x) for x in p["loc"]) or "<root>"
        lines.append(f"  - {loc}: {p['msg']}")
    return ReportError("\n".join(lines))


StepType = Literal[
    "plan",
    "tool_call",
    "llm_call",
    "critique",
    "revision",
    "code_exec",
]
RunStatus = Literal["succeeded", "failed", "timeout"]
CritiqueVerdict = Literal["PASS", "REVISE"]


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in: int = Field(default=0, ge=0)
    out: int = Field(default=0, ge=0)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    mime: str = "application/octet-stream"
    data_base64: str
    size: int = Field(default=0, ge=0)

    def decoded_bytes(self) -> bytes:
        import base64

        return base64.b64decode(self.data_base64)


class TraceStep(BaseModel):
    """One step of a run.

    ``parent_step_id`` is the key of the *step* that spawned it (usually the
    ``plan`` step that scheduled it); a run-level step has no parent. The
    report renders steps as an indented tree on this edge.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    type: StepType
    name: str = ""
    parent_step_id: Optional[str] = None
    tool_name: Optional[str] = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    error: Optional[str] = None
    verdict: Optional[CritiqueVerdict] = None
    artifacts: list[Artifact] = Field(default_factory=list)


class TraceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task: str
    status: RunStatus
    provider: Optional[str] = None
    model: Optional[str] = None
    steps: list[TraceStep]
    final_output: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    schema_version: str = "1.0"

    def total_cost_usd(self) -> float:
        return round(sum(s.cost_usd for s in self.steps), 6)

    def total_latency_ms(self) -> int:
        return sum(s.latency_ms for s in self.steps)

    def total_tokens(self) -> TokenUsage:
        return TokenUsage(
            in=sum(s.tokens.in for s in self.steps),
            out=sum(s.tokens.out for s in self.steps),
        )

    def tree(self) -> "tuple[TraceStep, list[TraceStep]]":
        """Return (root, all_steps_in_tree_order).

        Steps whose parent is absent from the run are attached to the root so
        a truncated trace still renders; siblings keep input order.
        """
        by_parent: dict[Optional[str], list[TraceStep]] = {}
        for s in self.steps:
            by_parent.setdefault(s.parent_step_id, []).append(s)
        roots = by_parent.get(None, [])
        ordered: list[TraceStep] = []
        seen: set[str] = set()

        def walk(steps: list[TraceStep]) -> None:
            for s in steps:
                if s.step_id in seen:
                    continue
                seen.add(s.step_id)
                ordered.append(s)
                walk(by_parent.get(s.step_id, []))

        walk(roots)
        if roots:
            return roots[0], ordered
        return self.steps[0], self.steps

    def iter_tree(self) -> "list[tuple[TraceStep, int]]":
        """Every step in tree (pre-order) with its indent depth, root = 0.

        Siblings keep input order; a step whose parent is absent is treated
        as a root. Depth is the length of the ancestor chain.
        """
        by_parent: dict[Optional[str], list[TraceStep]] = {}
        for s in self.steps:
            by_parent.setdefault(s.parent_step_id, []).append(s)
        known = {s.step_id for s in self.steps}
        out: list[tuple[TraceStep, int]] = []

        def walk(steps: list[TraceStep], depth: int, seen: set[str]) -> None:
            for s in steps:
                if s.step_id in seen:
                    continue
                seen.add(s.step_id)
                out.append((s, depth))
                walk(by_parent.get(s.step_id, []), depth + 1, seen)

        roots = by_parent.get(None, [])
        orphans = [s for s in self.steps if s.parent_step_id is not None and s.parent_step_id not in known]
        seen: set[str] = set()
        walk(roots, 0, seen)
        walk(orphans, 0, seen)
        for s in self.steps:
            if s.step_id not in seen:
                out.append((s, 0))
        return out


# ---------------------------------------------------------------------------
# Eval results
# ---------------------------------------------------------------------------

ScorerName = Literal[
    "schema",
    "numeric_tolerance",
    "code_test_pass_rate",
    "llm_judge",
]
TaskResult = Literal["PASS", "FAIL"]


class EvalTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    scorer: ScorerName
    result: TaskResult
    score: float = Field(ge=0.0, le=1.0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: int = Field(default=0, ge=0)
    detail: Optional[str] = None


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str
    config_hash: str
    model: str
    provider: str
    prompt_version: str
    dataset_version: str
    timestamp: str
    tasks: list[EvalTask]

    # --- aggregates (recomputed, never trusted from the file) --------------

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    @property
    def pass_count(self) -> int:
        return sum(1 for t in self.tasks if t.result == "PASS")

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.n_tasks if self.n_tasks else 0.0

    @property
    def avg_cost_usd(self) -> float:
        return (
            sum(t.cost_usd for t in self.tasks) / self.n_tasks
            if self.n_tasks
            else 0.0
        )

    @property
    def avg_latency_ms(self) -> float:
        return (
            sum(t.latency_ms for t in self.tasks) / self.n_tasks
            if self.n_tasks
            else 0.0
        )

    def latency_percentiles(self, p50: int = 50, p95: int = 95) -> tuple[int, int]:
        """Nearest-rank percentiles over task latencies (deterministic)."""
        vals = sorted(t.latency_ms for t in self.tasks)
        if not vals:
            return 0, 0

        def rank(p: int) -> int:
            return vals[max(0, min(len(vals) - 1, -(-p * len(vals) // 100) - 1))]

        return rank(p50), rank(p95)

    def regression(self, baseline: "EvalReport") -> list[EvalTask]:
        """Tasks that PASS at baseline but FAIL here."""
        base = {t.task: t for t in baseline.tasks}
        return [
            t for t in self.tasks if base.get(t.task, t).result == "PASS" and t.result == "FAIL"
        ]

    def improvement(self, baseline: "EvalReport") -> list[EvalTask]:
        """Tasks that FAIL at baseline but PASS here."""
        base = {t.task: t for t in baseline.tasks}
        return [
            t for t in self.tasks if base.get(t.task, t).result == "FAIL" and t.result == "PASS"
        ]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ReportError(f"input not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReportError(f"{p} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ReportError(f"{p}: top level must be a JSON object, got {type(data).__name__}")
    return data


def load_trace(path: str | Path) -> TraceRun:
    data = load_json(path)
    try:
        return TraceRun.model_validate(data)
    except ValidationError as e:
        raise _fail(f"trace {Path(path).name}", e)


def load_eval(path: str | Path) -> EvalReport:
    data = load_json(path)
    try:
        return EvalReport.model_validate(data)
    except ValidationError as e:
        raise _fail(f"eval {Path(path).name}", e)
