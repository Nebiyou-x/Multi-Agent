import os, uuid, psycopg2, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from packages.trace.src.trace.schemas import TraceRun, TraceStep
from packages.agent_core.src.llm import LLMClient
from packages.agent_core.src.planner import create_plan
from packages.agent_core.src.executor import execute_step
from packages.agent_core.src.critic import critique

app = FastAPI()
DB_URL = os.getenv("DATABASE_URL")
llm = LLMClient() # reads LLM_PROVIDER/MODEL from env

def persist_run(run: TraceRun):
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
        out, tool_out, meta = await execute_step(req.task, st, scratchpad, llm)
        scratchpad[st.id] = out
        run.steps.append(TraceStep(type="tool_call" if st.tool else "llm_call", name=st.tool or "reason", input={"subtask": st.model_dump(), "tool_output": tool_out}, output={"result": out}, tokens={"in": meta["tokens_in"], "out": meta["tokens_out"]}, cost_usd=meta["cost_usd"], latency_ms=meta["latency_ms"]))

    final_output = "\n\n".join(scratchpad.values())

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

    run.final_output = {"answer": final_output}
    run.status = "succeeded"
    persist_run(run)
    return run

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