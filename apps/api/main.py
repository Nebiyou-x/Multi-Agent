import base64
import os, uuid, psycopg2, json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from packages.trace.src.trace.schemas import TraceRun, TraceStep
from packages.agent_core.llm import LLMClient
from packages.agent_core.planner import create_plan
from packages.agent_core.executor import execute_step
from packages.agent_core.critic import critique

app = FastAPI()
DB_URL = os.getenv("DATABASE_URL")
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "data/artifacts"))
llm = LLMClient() # reads LLM_PROVIDER/MODEL from env


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
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO runs (run_id, task, status, final_output) VALUES (%s,%s,%s,%s) ON CONFLICT (run_id) DO UPDATE SET status=%s, final_output=%s",
                        (run.run_id, run.task, run.status, json.dumps(run.final_output), run.status, json.dumps(run.final_output)))
            for s in run.steps:
                cur.execute("INSERT INTO steps (step_id, run_id, type, name, input, output, latency_ms, tokens, cost_usd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (s.step_id, run.run_id, s.type, s.name, json.dumps(s.input), json.dumps(s.output), s.latency_ms, json.dumps(s.tokens), s.cost_usd))
        conn.commit()

class TaskRequest(BaseModel):
    task: str

@app.post("/runs")
async def create_run(req: TaskRequest):
    run = TraceRun(task=req.task, status="running")
    scratchpad = {}
    
    # PLANNING
    plan, meta = await create_plan(req.task, llm)
    run.steps.append(TraceStep(type="plan", name=f"planner:{meta['model']}", input={"task": req.task}, output=plan.model_dump(), tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]}, cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))
    
    # EXECUTING
    for st in plan.steps:
        out, tool_out, err, meta = await execute_step(req.task, st, scratchpad, llm)
        scratchpad[st.id] = out
        run.steps.append(TraceStep(type="tool_call" if st.tool else "llm_call", name=st.tool or "reason",
                                   input={"subtask": st.model_dump(), "tool_output": tool_out},
                                   output={"result": out},
                                   error=err,
                                   tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]},
                                   cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))

    # Only step results (s1, s2, ...) - scratchpad also holds _tool_output_*/_tool_failures
    final_output = "\n\n".join(v for k, v in scratchpad.items() if not k.startswith("_"))

    # CRITIQUING + REVISING LOOP
    max_rev = int(os.getenv("MAX_REVISIONS", 3))
    for i in range(max_rev):
        verdict, meta = await critique(req.task, scratchpad, final_output, llm)
        run.steps.append(TraceStep(type="critique", name=f"critic:{meta['model']}", input={"output": final_output}, output=verdict.model_dump(), tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]}, cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))
        if verdict.verdict == "PASS":
            break
        # REVISING - one more LLM pass with feedback
        revise_resp = await llm.chat(system="You are revising output based on critic feedback.", user=f"FEEDBACK: {verdict.feedback}\nOUTPUT: {final_output}\nImprove it.")
        final_output = revise_resp.content
        run.steps.append(TraceStep(type="revision", name="reviser", input={"feedback": verdict.feedback}, output={"revised": final_output}, tokens={"in": revise_resp.tokens_in, "out": revise_resp.tokens_out}, cost_usd=revise_resp.cost_usd, latency_ms=revise_resp.latency_ms))

    # List any chart/image artifacts the run produced so the answer can point at them
    produced = []
    for step in run.steps:
        arts = (step.input.get("tool_output") or {}).get("artifacts") or []
        produced.extend(f"/artifacts/{run.run_id}/{a['name']}" for a in arts if a.get("content_b64"))
    run.final_output = {"answer": final_output, "artifacts": list(dict.fromkeys(produced))}  # dedupe
    run.status = "succeeded"
    persist_run(run)
    return run


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

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, task, status, final_output FROM runs WHERE run_id=%s", (run_id,))
            row = cur.fetchone()
            if not row: raise HTTPException(404)
            cur.execute("SELECT step_id, type, name, input, output, latency_ms, tokens, cost_usd FROM steps WHERE run_id=%s ORDER BY started_at", (run_id,))
            steps = cur.fetchall()
    return {"run_id": row[0], "task": row[1], "status": row[2], "final_output": row[3], "steps": steps}

@app.get("/health")
def health(): return {"ok": True, "provider": llm.provider, "model": llm.model}