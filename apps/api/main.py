import base64
import os, json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from packages.trace.src.trace.schemas import TraceRun, TraceStep
from packages.agent_core.llm import LLMClient, COST_PER_1K
from packages.agent_core.planner import create_plan
from packages.agent_core.executor import execute_step
from packages.agent_core.critic import critique

app = FastAPI()
DB_URL = os.getenv("DATABASE_URL")
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "data/artifacts"))
llm = LLMClient() # reads LLM_PROVIDER/MODEL from env

# The trace viewer runs in a browser on :3000 talking to the API on :8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _connect():
    import psycopg2
    return psycopg2.connect(DB_URL)


def migrate_schema() -> None:
    """Idempotent in-place migration for the extra viewer columns so the API
    works against databases created from an older init.sql."""
    conn = _connect()  # also proves the DB is reachable at startup
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS provider TEXT")
            cur.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS model TEXT")
            cur.execute("ALTER TABLE steps ADD COLUMN IF NOT EXISTS parent_step_id UUID REFERENCES steps(step_id) ON DELETE SET NULL")
            cur.execute("ALTER TABLE steps ADD COLUMN IF NOT EXISTS error TEXT")
            cur.execute("ALTER TABLE steps ADD COLUMN IF NOT EXISTS seq INT")
        conn.commit()
    finally:
        conn.close()

migrate_schema()


def persist_artifacts(run: TraceRun) -> None:
    """Write sandbox artifacts (charts, CSVs) to disk so the final answer can
    reference them and the UI can serve them. Called after each run."""
    for step in run.steps:
        artifacts = (step.input.get("tool_output") or {}).get("artifacts") or []
        for art in artifacts:
            if not art.get("content_b64"):
                continue  # truncated / too large - only name+size recorded
            target = ARTIFACT_DIR / str(run.run_id) / art["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(art["content_b64"]))


def persist_run(run: TraceRun):
    persist_artifacts(run)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO runs (run_id, task, status, final_output, provider, model) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO UPDATE SET status=%s, final_output=%s, provider=%s, model=%s",
                (run.run_id, run.task, run.status, json.dumps(run.final_output),
                 getattr(run, "provider", None), getattr(run, "model", None),
                 run.status, json.dumps(run.final_output),
                 getattr(run, "provider", None), getattr(run, "model", None)))
            for seq, s in enumerate(run.steps):
                cur.execute(
                    "INSERT INTO steps (step_id, run_id, parent_step_id, seq, type, name, input, output, error, latency_ms, tokens, cost_usd) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (s.step_id, run.run_id, s.parent_step_id, seq, s.type, s.name,
                     json.dumps(s.input), json.dumps(s.output), s.error,
                     s.latency_ms, json.dumps(s.tokens), s.cost_usd))
        conn.commit()


class TaskRequest(BaseModel):
    task: str
    provider: str | None = None  # replay: re-run with a different provider/model
    model: str | None = None


async def _run_pipeline(task: str, provider: str | None, model: str | None) -> tuple[TraceRun, LLMClient]:
    """The planner -> executor -> critic loop, with optional model override (replay)."""
    run = TraceRun(task=task, status="running")
    step_llm = LLMClient(provider=provider, model=model) if (provider or model) else llm
    scratchpad = {}

    # PLANNING
    plan, meta = await create_plan(task, step_llm)
    run.steps.append(TraceStep(type="plan", name=f"planner:{meta['model']}", input={"task": task}, output=plan.model_dump(),
                               tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]},
                               cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))

    # EXECUTING
    for st in plan.steps:
        out, tool_out, err, meta = await execute_step(task, st, scratchpad, step_llm)
        scratchpad[st.id] = out
        run.steps.append(TraceStep(type="tool_call" if st.tool else "llm_call", name=st.tool or "reason",
                                   input={"subtask": st.model_dump(), "tool_output": tool_out},
                                   output={"result": out},
                                   error=err,
                                   tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]},
                                   cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))

    # Only step results (s1, s2, ...) - scratchpad also holds _tool_output_*/_tool_failures keys
    final_output = "\n\n".join(v for k, v in scratchpad.items() if not k.startswith("_"))

    # CRITIQUING + REVISING LOOP
    max_rev = int(os.getenv("MAX_REVISIONS", 3))
    for i in range(max_rev):
        verdict, meta = await critique(task, scratchpad, final_output, step_llm)
        critique_step = TraceStep(type="critique", name=f"critic:{meta['model']}",
                                  input={"output": final_output}, output=verdict.model_dump(),
                                  tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]},
                                  cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"])
        run.steps.append(critique_step)
        if verdict.verdict == "PASS":
            break
        # REVISING - one more LLM pass with feedback; nest it under its critique
        revise_resp = await step_llm.chat(system="You are revising output based on critic feedback.",
                                          user=f"FEEDBACK: {verdict.feedback}\nOUTPUT: {final_output}\nImprove it.")
        final_output = revise_resp.content
        revise_step = TraceStep(type="revision", name="reviser",
                                input={"feedback": verdict.feedback}, output={"revised": final_output},
                                parent_step_id=critique_step.step_id,
                                tokens={"in": revise_resp.tokens_in, "out": revise_resp.tokens_out},
                                cost_usd=revise_resp.cost_usd, latency_ms=revise_resp.latency_ms)
        run.steps.append(revise_step)

    # List any chart/image artifacts the run produced so the answer can point at them
    produced = []
    for step in run.steps:
        arts = (step.input.get("tool_output") or {}).get("artifacts") or []
        produced.extend(f"/artifacts/{run.run_id}/{a['name']}" for a in arts if a.get("content_b64"))
    run.final_output = {"answer": final_output, "artifacts": list(dict.fromkeys(produced))}  # dedupe
    run.status = "succeeded"
    run.provider = step_llm.provider
    run.model = step_llm.model
    persist_run(run)
    return run, step_llm

@app.post("/runs")
async def create_run(req: TaskRequest):
    run, step_llm = await _run_pipeline(req.task, req.provider, req.model)
    return _run_payload(run)


def _run_payload(run: TraceRun) -> dict:
    return {
        "run_id": run.run_id,
        "task": run.task,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "created_at": run.created_at.isoformat(),
        "final_output": run.final_output,
        "steps": [
            {"step_id": s.step_id, "parent_step_id": s.parent_step_id, "type": s.type, "name": s.name,
             "input": s.input, "output": s.output, "error": s.error,
             "latency_ms": s.latency_ms, "tokens": s.tokens, "cost_usd": s.cost_usd}
            for s in run.steps
        ],
    }


@app.get("/runs")
def list_runs(limit: int = 50):
    """Run list for the viewer: task, status, duration, total cost, step count."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.run_id, r.task, r.status, r.provider, r.model, r.created_at, "
                "COALESCE(SUM(s.cost_usd), 0) AS total_cost, "
                "COALESCE(SUM(s.latency_ms), 0) AS total_ms, COUNT(s.step_id) AS n_steps "
                "FROM runs r LEFT JOIN steps s ON s.run_id = r.run_id "
                f"GROUP BY r.run_id, r.task, r.status, r.provider, r.model, r.created_at "
                f"ORDER BY r.created_at DESC LIMIT {int(limit)}")
            rows = cur.fetchall()
    return [{"run_id": str(r[0]), "task": r[1], "status": r[2], "provider": r[3], "model": r[4],
             "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else r[5],
             "cost_usd": round(float(r[6]), 4), "duration_ms": int(r[7]), "n_steps": int(r[8])}
            for r in rows]


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, task, status, provider, model, final_output, created_at FROM runs WHERE run_id=%s", (run_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "run not found")
            cur.execute(
                "SELECT step_id, parent_step_id, seq, type, name, input, output, error, latency_ms, tokens, cost_usd "
                "FROM steps WHERE run_id=%s ORDER BY seq, started_at", (run_id,))
            steps = cur.fetchall()
    payload = {
        "run_id": str(row[0]), "task": row[1], "status": row[2],
        "provider": row[3], "model": row[4], "final_output": row[5],
        "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else row[6],
    }
    payload["steps"] = [
        {"step_id": str(s[0]), "parent_step_id": str(s[1]) if s[1] else None, "type": s[3], "name": s[4],
         "input": s[5], "output": s[6], "error": s[7],
         "latency_ms": s[8], "tokens": s[9], "cost_usd": s[10]}
        for s in steps
    ]
    return payload


@app.get("/config")
def get_config():
    """What the replay UI can pick: available providers + known models + current defaults."""
    return {
        "default_provider": llm.provider,
        "default_model": llm.model,
        "providers": {
            "openai": [m for m in COST_PER_1K if m.startswith("gpt")],
            "anthropic": [m for m in COST_PER_1K if m.startswith("claude")],
            "gemini": [m for m in COST_PER_1K if m.startswith("gemini")],
        },
        "api_keys": {"openai": bool(os.getenv("OPENAI_API_KEY")),
                     "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
                     "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))},
    }

@app.get("/artifacts/{run_id}/{name}")
def get_artifact(run_id: str, name: str):
    # Path traversal guard: the target must resolve to exactly
    # <ARTIFACT_DIR>/<run_id>/<name> (no "..", no nested separators)
    if "/" in name or "\\" in name or ".." in name or "/" in run_id or ".." in run_id:
        raise HTTPException(400, "bad artifact path")
    target = (ARTIFACT_DIR / run_id / name).resolve()
    if ARTIFACT_DIR.resolve() not in target.parents or target.name != name:
        raise HTTPException(400, "bad artifact path")
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)

@app.get("/health")
def health(): return {"ok": True, "provider": llm.provider, "model": llm.model}
