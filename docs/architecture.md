# Agent Platform - Architecture v0

## 1. Flow
Task -> Planner -> Executor -> Tool Sandbox (Docker) -> Critic -> Loop -> Final Output

```mermaid
graph TD
    User-->API[API / Orchestrator]
    API-->Planner
    Planner-->State{State Machine}
    State-->|PLANNING| LLM
    State-->|EXECUTING| Executor
    Executor-->Registry[Tool Registry]
    Registry-->Sandbox[Sandbox Manager - Docker]
    Sandbox-->Trace[Trace Recorder]
    Trace-->Critic
    Critic-->State
    State-->|DONE/FAILED| Output
    Trace-->DB[(Postgres)]
    Trace-->UI[Trace UI]
```

## Trace schema 
```
{
  "run_id": "uuid",
  "task": "string",
  "steps": [
    {
      "step_id": 1,
      "type": "plan|tool_call|llm_call|critique|revision",
      "input": {},
      "output": {},
      "tokens": {"in": 0, "out": 0},
      "latency_ms": 0,
      "cost_usd": 0.0,
      "parent_step_id": null
    }
  ],
  "status": "succeeded|failed|timeout",
  "final_output": {}
}
```