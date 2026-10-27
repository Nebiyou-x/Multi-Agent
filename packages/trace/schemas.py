from pydantic import BaseModel, Field
from typing import Literal, Optional, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

StepType = Literal["plan", "tool_call", "llm_call", "critique", "revision"]
RunStatus = Literal["running", "succeeded", "failed", "timeout"]

class TraceStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    parent_step_id: Optional[str] = None
    type: StepType
    name: str # e.g. "planner:gpt-4o", "tool:code_exec"
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    latency_ms: int = 0
    tokens: dict = Field(default_factory=lambda: {"in": 0, "out": 0})
    cost_usd: float = 0.0

class TraceRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    task: str
    status: RunStatus = "running"
    steps: List[TraceStep] = Field(default_factory=list)
    final_output: Optional[Any] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Helper to enforce contract
    def add_step(self, step: TraceStep):
        self.steps.append(step)
        self.updated_at = datetime.now(timezone.utc)