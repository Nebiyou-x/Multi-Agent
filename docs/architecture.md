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