"""Scan a reports/ tree and write a deterministic ``index.json``.

The Next.js list pages (``/traces``, ``/evals``) read this file at build
time instead of scanning the filesystem themselves, so the index is the
single source for what exists. Output is byte-stable: entries sorted by
name, dict keys sorted, no timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schema import load_eval, load_trace


def _trace_entry(p: Path) -> dict:
    try:
        t = load_trace(p)
        return {
            "run_id": t.run_id,
            "task": t.task,
            "status": t.status,
            "model": t.model,
            "provider": t.provider,
            "n_steps": len(t.steps),
            "total_cost_usd": t.total_cost_usd(),
            "total_latency_ms": t.total_latency_ms(),
            "finished_at": t.finished_at or t.started_at,
            "file": p.name,
        }
    except Exception as e:  # a broken trace still appears, flagged
        return {"file": p.name, "invalid": True, "error": str(e)}


def _eval_entry(p: Path, reports_dir: Path) -> dict:
    try:
        r = load_eval(p)
        return {
            "config_id": r.config_id,
            "model": r.model,
            "provider": r.provider,
            "timestamp": r.timestamp,
            "n_tasks": r.n_tasks,
            "pass_rate": round(r.pass_rate, 4),
            "avg_cost_usd": round(r.avg_cost_usd, 6),
            "file": p.name,
        }
    except Exception as e:
        return {"file": p.name, "invalid": True, "error": str(e)}


def build_index(reports_root: str | Path) -> Path:
    root = Path(reports_root)
    index: dict = {"traces": [], "evals": []}

    traces_dir = root / "traces"
    if traces_dir.is_dir():
        for p in sorted(traces_dir.glob("*.json")):
            index["traces"].append(_trace_entry(p))

    evals_dir = root / "evals"
    if evals_dir.is_dir():
        for p in sorted(evals_dir.glob("*.json")):
            entry = _eval_entry(p, root)
            has_md = (evals_dir / f"{p.stem}.md").exists()
            has_html = (evals_dir / f"{p.stem}.html").exists()
            entry["has_markdown"] = has_md
            entry["has_html"] = has_html
            index["evals"].append(entry)

    out = root / "index.json"
    out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
