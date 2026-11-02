"""One-shot generator for the committed demo artifacts under reports/.

Writes:
  reports/traces/demo-inflation-analysis.json   (hand-authored trace, two real PNGs)
  reports/evals/2025-11-15_v1.json
  reports/evals/2025-11-20_v2.json
  reports/evals/2025-11-25_v3.json
  reports/evals/charts/pass_rate_v1_v2_v3.png   (combined chart, spec deliverable 4)

Run:  .venv/bin/python scripts/make_demo_artifacts.py
Idempotent: overwrites the demo inputs. Everything is deterministic.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent


def _png_bytes(figsize: tuple[float, float], title: str, bars: list[str], vals: list[float], colored: bool = False) -> bytes:
    import io

    plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "savefig.facecolor": "white"})
    fig, ax = plt.subplots(figsize=figsize)
    colors = ["#1f6f43" if (v >= 0 or not colored) else "#b23b3b" for v in vals] if colored else ["#3a6ea5" for _ in vals]
    ax.bar(range(len(vals)), vals, color=colors)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(bars, rotation=45, ha="right", fontsize=7)
    ax.axhline(0, color="#8a93a2", linewidth=0.8)
    ax.set_title(title)
    ax.grid(axis="y", linewidth=0.5, alpha=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


_YEARS = [str(y) for y in range(2015, 2025)]
_SERIES = [14.2, 25.8, 30.9, 34.1, 23.5, 17.2, 12.4, 9.8, 11.3, 7.6]
_YOY = [round(b - a, 1) for a, b in zip(_SERIES, _SERIES[1:])]
INFLATION_V1 = _png_bytes((4.2, 2.4), "Ethiopia annual inflation %", _YEARS, _SERIES, colored=True)
INFLATION_V2 = _png_bytes((4.2, 2.4), "Ethiopia YoY inflation change pp", _YEARS[1:], _YOY, colored=True)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


WORLD_BANK_SNIPPET = json.dumps(
    [
        {"id": "FP.CPI.TOTL.ZG", "value": 14.16, "date": "2015"},
        {"id": "FP.CPI.TOTL.ZG", "value": 25.84, "date": "2016"},
        {"id": "FP.CPI.TOTL.ZG", "value": 30.95, "date": "2017"},
        {"id": "FP.CPI.TOTL.ZG", "value": 34.11, "date": "2018"},
        {"id": "FP.CPI.TOTL.ZG", "value": 23.53, "date": "2019"},
        {"id": "FP.CPI.TOTL.ZG", "value": 17.18, "date": "2020"},
        {"id": "FP.CPI.TOTL.ZG", "value": 12.40, "date": "2021"},
        {"id": "FP.CPI.TOTL.ZG", "value": 9.83, "date": "2022"},
        {"id": "FP.CPI.TOTL.ZG", "value": 11.33, "date": "2023"},
        {"id": "FP.CPI.TOTL.ZG", "value": 7.62, "date": "2024"},
    ],
    indent=1,
)

CODE_V1 = """import json, pathlib, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

data = json.loads(pathlib.Path("/in/http_fetch_s2.json").read_text())
years = [int(d["date"]) for d in data]
rates = [d["value"] for d in data]
fig, ax = plt.subplots()
ax.bar(years, rates)
fig.savefig("/out/inflation.png")"""

CODE_V2 = CODE_V1 + """
diffs = [b - a for a, b in zip(rates, rates[1:])]
ax.set_xticks(years[1:])
ax.set_xticklabels(years[1:], rotation=45)
ax.axhline(0, color="gray", linewidth=0.8)
ax.set_title("Ethiopia annual inflation (YoY deltas)")"""


def trace_fixture() -> dict:
    art_v1 = {"name": "inflation.png", "mime": "image/png", "data_base64": b64(INFLATION_V1), "size": len(INFLATION_V1)}
    art_v2 = {"name": "inflation.png", "mime": "image/png", "data_base64": b64(INFLATION_V2), "size": len(INFLATION_V2)}
    world = {
        "name": "worldbank_eth_cpi.json",
        "mime": "application/json",
        "data_base64": b64(WORLD_BANK_SNIPPET.encode()),
        "size": len(WORLD_BANK_SNIPPET.encode()),
    }
    return {
        "run_id": "3f8a2c71-9d4e-4b6a-8c1e-7a5d92f0b3a1",
        "task": "Download Ethiopia's annual inflation (CPI) data from the World Bank API, compute year-over-year change, and save a line chart to /out/inflation.png",
        "status": "succeeded",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "schema_version": "1.0",
        "started_at": "2025-11-20T09:14:02Z",
        "finished_at": "2025-11-20T09:16:48Z",
        "steps": [
            {
                "step_id": "s1",
                "type": "plan",
                "name": "planner:gpt-4o-mini",
                "parent_step_id": None,
                "input": {"task": "eth-inflation", "n_subtasks": 5},
                "output": {
                    "plan": [
                        {"id": "s2", "tool": "http_fetch", "desc": "Fetch World Bank Ethiopia CPI series"},
                        {"id": "s3", "tool": "code_exec", "desc": "Compute YoY change, plot line chart to /out/inflation.png"},
                        {"id": "s4", "tool": None, "desc": "Verify chart exists and report findings"},
                    ]
                },
                "tokens": {"in": 812, "out": 404},
                "latency_ms": 2410,
                "cost_usd": 0.0041,
            },
            {
                "step_id": "s2",
                "type": "tool_call",
                "name": "tool:http_fetch",
                "tool_name": "http_fetch",
                "parent_step_id": "s1",
                "input": {"url": "https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json&date=2015:2024"},
                "output": {
                    "status_code": 200,
                    "bytes": len(WORLD_BANK_SNIPPET),
                    "saved_to": "/in/http_fetch_s2.json",
                    "artifacts": [world],
                    "summary": "10 data points, 2015-2024, FP.CPI.TOTL.ZG",
                },
                "tokens": {"in": 0, "out": 0},
                "latency_ms": 842,
                "cost_usd": 0.0,
                "artifacts": [world],
            },
            {
                "step_id": "s3",
                "type": "code_exec",
                "name": "tool:code_exec",
                "tool_name": "code_exec",
                "parent_step_id": "s1",
                "input": {"code": CODE_V1, "language": "python", "mounts": ["/in/http_fetch_s2.json"]},
                "output": {"exit_code": 0, "stdout": "wrote /out/inflation.png (18,214 bytes)", "stderr": "", "artifacts": [art_v1]},
                "tokens": {"in": 1496, "out": 618},
                "latency_ms": 6120,
                "cost_usd": 0.0086,
                "artifacts": [art_v1],
            },
            {
                "step_id": "s4",
                "type": "critique",
                "name": "critic:gpt-4o-mini",
                "parent_step_id": "s1",
                "input": {"iter": 1, "max": 3},
                "output": {
                    "verdict": "REVISE",
                    "score": 0.55,
                    "feedback": "The chart plots the raw series but the task asked for year-over-year change. The x-axis is also missing; add YoY deltas and labelled ticks.",
                },
                "tokens": {"in": 623, "out": 287},
                "latency_ms": 1830,
                "cost_usd": 0.0032,
                "verdict": "REVISE",
            },
            {
                "step_id": "s5",
                "type": "revision",
                "name": "reviser:gpt-4o-mini",
                "parent_step_id": "s4",
                "input": {"feedback": "plot YoY deltas, label x-axis"},
                "output": {"revised": "Rewrite the plotting step: compute diffs with zip(), set x-ticks to years[1:], add a zero line, retitling to YoY deltas."},
                "tokens": {"in": 704, "out": 512},
                "latency_ms": 2210,
                "cost_usd": 0.0051,
            },
            {
                "step_id": "s6",
                "type": "code_exec",
                "name": "tool:code_exec",
                "tool_name": "code_exec",
                "parent_step_id": "s5",
                "input": {"code": CODE_V2, "language": "python", "mounts": ["/in/http_fetch_s2.json"]},
                "output": {"exit_code": 0, "stdout": "wrote /out/inflation.png (21,406 bytes)", "stderr": "", "artifacts": [art_v2]},
                "tokens": {"in": 1540, "out": 663},
                "latency_ms": 5940,
                "cost_usd": 0.0089,
                "artifacts": [art_v2],
            },
        ],
        "final_output": {
            "answer": "Ethiopia's headline CPI inflation peaked at 34.1% in 2018 and has since eased to 7.6% in 2024. The YoY deltas are largest in 2017 (+5.1) and 2018 (+3.2); every year after 2018 is a negative delta (disinflation). Chart saved to /out/inflation.png.",
            "artifacts": [art_v2],
        },
    }


N_TASKS = 100


def _task_names() -> list[str]:
    return [f"task-{i:03d}" for i in range(1, N_TASKS + 1)]


# Per task index (1-based): which scorers cycle, base cost, base latency.
_SCORERS = ["schema", "numeric_tolerance", "code_test_pass_rate", "llm_judge"]
_BASE_COST = [0.0018, 0.0021, 0.0062, 0.0118]
_BASE_LAT = [880, 1010, 4300, 6600]


# Explicit fail-sets per config (task numbers, 1-based). Everything else passes.
FAIL_V1 = set(range(69, 101))            # 32 fails -> 68%
FAIL_V2 = set(range(76, 101))            # 25 fails -> 75%
# v3: 2 regressions (task-003, task-007 passed at v1 and now fail) plus 7 tasks
# that were already failing at v1 stay failing -> 9 fails total -> 91%.
FAIL_V3 = {3, 7, 94, 95, 96, 97, 98, 99, 100}


def _pass_fail(pattern: str) -> dict[str, tuple[str, float, str]]:
    """Deterministic task->(result, score, detail) map for a given config.

    v1 = 68%, v2 = 75%, v3 = 91% with exactly 2 PASS->FAIL regressions vs v1
    (task-003, task-007) and 25 FAIL->PASS improvements.
    """
    fails = {"v1": FAIL_V1, "v2": FAIL_V2, "v3": FAIL_V3}[pattern]
    names = _task_names()
    results: dict[str, tuple[str, float, str]] = {}
    for i, name in enumerate(names, start=1):
        passing = i not in fails
        if pattern == "v1":
            score, detail = (0.98, None) if passing else (0.31, "schema test 2/4")
        elif pattern == "v2":
            score, detail = (0.97, None) if passing else (0.44, "numeric delta > tol")
        else:
            if i in (3, 7):
                score, detail = 0.28, "regressed: now returns 501 on 5xx"
            else:
                score, detail = (0.99, None) if passing else (0.39, "code tests 4/6")
        results[name] = ("PASS" if passing else "FAIL", round(score, 2), detail)
    return results


def _count_pass(results: dict[str, tuple[str, float, str]]) -> int:
    return sum(1 for r in results.values() if r[0] == "PASS")


def eval_fixture(config_id: str, config_hash: str, prompt_version: str, timestamp: str, pattern: str) -> dict:
    results = _pass_fail(pattern)
    names = _task_names()
    # per-config cost drift (prompt version changes call size)
    drift = {"v1": 1.0, "v2": 1.06, "v3": 1.11}[pattern]
    tasks = []
    for i, name in enumerate(names):
        res, score, detail = results[name]
        base_cost = _BASE_COST[i % 4]
        base_lat = _BASE_LAT[i % 4]
        tasks.append(
            {
                "task": name,
                "scorer": _SCORERS[i % 4],
                "result": res,
                "score": score,
                "cost_usd": round(base_cost * drift, 6),
                "latency_ms": base_lat,
                "detail": detail,
            }
        )
    return {
        "config_id": config_id,
        "config_hash": config_hash,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "prompt_version": prompt_version,
        "dataset_version": "golden-2025-11",
        "timestamp": timestamp,
        "tasks": tasks,
    }


def main() -> None:
    tdir = ROOT / "reports" / "traces"
    edir = ROOT / "reports" / "evals"
    tdir.mkdir(parents=True, exist_ok=True)
    edir.mkdir(parents=True, exist_ok=True)

    (tdir / "demo-inflation-analysis.json").write_text(json.dumps(trace_fixture(), indent=2, sort_keys=True) + "\n")

    for fname, cfg, chash, pver, ts, pat in (
        ("2025-11-15_v1", "a3f9c2d18b4e", "p3", "2025-11-15T08:00:00Z", "v1"),
        ("2025-11-20_v2", "77e0d4b2a91c", "p4", "2025-11-20T08:00:00Z", "v2"),
        ("2025-11-25_v3", "5c21f8e0b7d3", "p5", "2025-11-25T08:00:00Z", "v3"),
    ):
        fx = eval_fixture(fname, chash, pver, ts, pat)
        (edir / f"{fname}.json").write_text(json.dumps(fx, indent=2, sort_keys=True) + "\n")
        print(f"{fname}: pass rate {_count_pass(_pass_fail(pat)) / N_TASKS * 100:.0f}%")

    # combined chart, deliverable 4
    import io

    plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "savefig.facecolor": "white"})
    fig, ax = plt.subplots(figsize=(4.4, 2.5))
    rates = [68.0, 75.0, 91.0]
    ax.bar(["v1", "v2", "v3"], rates, color=["#c7ccd6", "#3a6ea5", "#1f6f43"])
    ax.set_ylim(0, 100)
    for i, v in enumerate(rates):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9)
    ax.set_ylabel("pass rate (%)")
    ax.set_title("Pass rate across eval configs")
    buf = io.BytesIO()
    fig.savefig(buf)
    (edir / "charts" / "pass_rate_v1_v2_v3.png").parent.mkdir(parents=True, exist_ok=True)
    (edir / "charts" / "pass_rate_v1_v2_v3.png").write_bytes(buf.getvalue())
    print("demo artifacts written")


if __name__ == "__main__":
    main()
