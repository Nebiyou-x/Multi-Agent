"""Agent Forge static report generator.

Turns committed trace JSON and eval-results JSON into deterministic,
diffable artifacts: GitHub-renderable Markdown plus a self-contained HTML
report (inline CSS, base64 images, no network) that opens offline.

Determinism is a contract: the same input bytes produce the same output
bytes, run to run. No wall-clock value ever enters an output; all
timestamps shown come from the input files, and the generator version is
a fixed literal, not an install date.
"""

GENERATOR_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

from .schema import (  # noqa: F401
    Artifact,
    EvalReport,
    EvalTask,
    ReportError,
    TokenUsage,
    TraceRun,
    TraceStep,
    load_eval,
    load_trace,
)

__all__ = [
    "GENERATOR_VERSION",
    "SCHEMA_VERSION",
    "Artifact",
    "EvalReport",
    "EvalTask",
    "ReportError",
    "TokenUsage",
    "TraceRun",
    "TraceStep",
    "load_eval",
    "load_trace",
]
