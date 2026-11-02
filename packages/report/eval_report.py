"""Eval-results JSON -> Markdown + self-contained HTML + PNG charts.

Charts are produced with matplotlib's ``Agg`` backend and written next to the
report. They are byte-deterministic: no random seeds, fixed figure size,
sorted x-axis, and ``hash.seed``-free. Running the generator twice on the
same input yields identical PNG bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import GENERATOR_VERSION
from .schema import EvalReport, ReportError

_TPL_DIR = Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------

def _charts_dir(out_dir: Path, config_id: str) -> Path:
    d = out_dir / "charts" / config_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_charts(
    report: EvalReport,
    baseline: Optional[EvalReport],
    out_dir: Path,
) -> list[str]:
    """Return the relative paths (vs out_dir) of the charts just written."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "axes.grid": True,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.3,
            "font.size": 9,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        }
    )
    d = _charts_dir(Path(out_dir), report.config_id)

    paths: list[str] = []

    # 1. pass rate across the available configs
    series = []
    if baseline is not None:
        series.append((f"baseline ({baseline.config_id})", baseline.pass_rate * 100))
    series.append((report.config_id, report.pass_rate * 100))
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    names = [s[0] for s in series]
    vals = [s[1] for s in series]
    colors = ["#c7ccd6" if baseline and i == 0 else "#1f6f43" for i in range(len(names))]
    ax.bar(names, vals, color=colors)
    ax.set_ylim(0, 100)
    ax.set_ylabel("pass rate (%)")
    ax.set_title("Pass rate by config")
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=9)
    p1 = d / "pass_rate.png"
    fig.savefig(p1)
    plt.close(fig)
    paths.append(f"charts/{report.config_id}/pass_rate.png")

    # 2. cost per task
    tasks = sorted(report.tasks, key=lambda t: t.task)
    costs = [t.cost_usd for t in tasks]
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ax.bar(range(len(tasks)), costs, color=["#1f6f43" if t.result == "PASS" else "#b23b3b" for t in tasks])
    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels([t.task[:14] for t in tasks], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("cost (USD)")
    ax.set_title("Cost per task (green=PASS, red=FAIL)")
    p2 = d / "cost_per_task.png"
    fig.savefig(p2)
    plt.close(fig)
    paths.append(f"charts/{report.config_id}/cost_per_task.png")

    # 3. latency distribution
    lat = sorted(t.latency_ms for t in report.tasks)
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ax.hist(lat, bins=min(12, max(4, len(lat) // 2)), color="#3a6ea5", edgecolor="white")
    ax.set_xlabel("latency (ms)")
    ax.set_ylabel("tasks")
    p50, p95 = report.latency_percentiles()
    ax.axvline(p50, color="#b23b3b", linestyle="--", linewidth=1)
    ax.axvline(p95, color="#1f6f43", linestyle="--", linewidth=1)
    ax.set_title(f"Latency distribution (p50={p50} ms, p95={p95} ms)")
    p3 = d / "latency_dist.png"
    fig.savefig(p3)
    plt.close(fig)
    paths.append(f"charts/{report.config_id}/latency_dist.png")

    return paths


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _fmt_cost(v: float) -> str:
    return "$0.00" if v == 0 else f"${v:.4f}"


def _fmt_ms(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f} ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f} s"
    return f"{ms // 60_000} m {ms % 60_000 // 1000} s"


def render_markdown(
    report: EvalReport,
    baseline: Optional[EvalReport],
    chart_paths: list[str],
) -> str:
    p50, p95 = report.latency_percentiles()
    lines = [
        f"# Eval — {report.config_id}",
        "",
        f"- model: {report.model} ({report.provider})",
        f"- prompt v{report.prompt_version} · dataset v{report.dataset_version}",
        f"- config hash `{report.config_hash}` · {report.timestamp}",
        "",
        "## Aggregate",
        "",
        "| pass rate | avg cost | avg latency | p50 | p95 | tasks |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| {report.pass_rate * 100:.0f}% | {_fmt_cost(report.avg_cost_usd)} "
        f"| {_fmt_ms(report.avg_latency_ms)} | {_fmt_ms(p50)} | {_fmt_ms(p95)} | {report.n_tasks} |",
        "",
    ]

    if baseline is not None:
        bp50, bp95 = baseline.latency_percentiles()
        lines += [
            f"### vs baseline {baseline.config_id}",
            "",
            "| | this | baseline |",
            "| --- | --- | --- |",
            f"| pass rate | {report.pass_rate * 100:.0f}% | {baseline.pass_rate * 100:.0f}% |",
            f"| avg cost | {_fmt_cost(report.avg_cost_usd)} | {_fmt_cost(baseline.avg_cost_usd)} |",
            f"| p50 | {_fmt_ms(p50)} | {_fmt_ms(bp50)} |",
            f"| p95 | {_fmt_ms(p95)} | {_fmt_ms(bp95)} |",
            "",
        ]
        regs = report.regression(baseline)
        imps = report.improvement(baseline)
        if regs:
            lines += ["## Regressions (PASS -> FAIL)", ""]
            for t in regs:
                lines.append(f"- `{t.task}` — {t.scorer}: {t.detail or 'failed'}")
            lines.append("")
        if imps:
            lines += ["## Improvements (FAIL -> PASS)", ""]
            for t in imps:
                lines.append(f"- `{t.task}` — {t.scorer}")
            lines.append("")

    lines += [
        "## Per task",
        "",
        "| task | scorer | result | score | cost | latency |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for t in sorted(report.tasks, key=lambda t: t.task):
        lines.append(
            f"| {t.task} | {t.scorer} | {t.result} | {t.score:.2f} "
            f"| {_fmt_cost(t.cost_usd)} | {_fmt_ms(t.latency_ms)} |"
        )
    lines.append("")

    lines += ["## Charts", ""]
    for p in chart_paths:
        lines.append(f"![]({p})")
    lines.append("")

    lines += [
        "---",
        "",
        f"config hash `{report.config_hash}` · report {GENERATOR_VERSION} · {report.timestamp}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML (self-contained: inline CSS, base64 images)
# ---------------------------------------------------------------------------

def render_html(
    report: EvalReport,
    baseline: Optional[EvalReport],
    chart_paths: list[str],
    out_dir: Path,
) -> str:
    import base64

    env = Environment(
        loader=FileSystemLoader(str(_TPL_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("eval.html.j2")

    def b64(rel: str) -> str:
        p = Path(out_dir) / rel
        if not p.exists():
            return ""
        data = p.read_bytes()
        mime = "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    charts = [
        {"rel": rel, "data_url": b64(rel), "label": _chart_label(rel)}
        for rel in chart_paths
    ]
    p50, p95 = report.latency_percentiles()

    def delta(this_v: float, base_v: float) -> str:
        if base_v == 0:
            return ""
        return f"{(this_v - base_v) / base_v * 100:+.0f}%"

    rows = []
    base = {t.task: t for t in baseline.tasks} if baseline else {}
    for t in sorted(report.tasks, key=lambda t: t.task):
        b = base.get(t.task)
        rows.append(
            {
                "task": t.task,
                "scorer": t.scorer,
                "result": t.result,
                "score": t.score,
                "cost": _fmt_cost(t.cost_usd),
                "latency": _fmt_ms(t.latency_ms),
                "delta_result": (
                    ""
                    if b is None or b.result == t.result
                    else ("PASS->FAIL" if b.result == "PASS" else "FAIL->PASS")
                ),
                "regressed": bool(b and b.result == "PASS" and t.result == "FAIL"),
                "improved": bool(b and b.result == "FAIL" and t.result == "PASS"),
                "detail": t.detail,
            }
        )

    ctx = {
        "report": report,
        "baseline": baseline,
        "p50": _fmt_ms(p50),
        "p95": _fmt_ms(p95),
        "pass_rate": f"{report.pass_rate * 100:.0f}%",
        "avg_cost": _fmt_cost(report.avg_cost_usd),
        "avg_latency": _fmt_ms(report.avg_latency_ms),
        "charts": charts,
        "rows": rows,
        "regressions": report.regression(baseline) if baseline else [],
        "improvements": report.improvement(baseline) if baseline else [],
        "delta_pass": (
            delta(report.pass_rate * 100, baseline.pass_rate * 100) if baseline else ""
        ),
        "gen_version": GENERATOR_VERSION,
        "timestamp": report.timestamp,
        "full_json": json.dumps(
            {"config": report.model_dump(exclude={"tasks"}), "tasks": [t.model_dump() for t in sorted(report.tasks, key=lambda t: t.task)]},
            sort_keys=True,
            indent=2,
        ),
    }
    return tpl.render(**ctx)


def _chart_label(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    return {"pass_rate.png": "pass rate by config", "cost_per_task.png": "cost per task", "latency_dist.png": "latency distribution"}.get(
        name, name
    )


def write_outputs(
    report: EvalReport,
    baseline: Optional[EvalReport],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = report.config_id
    chart_paths = make_charts(report, baseline, out_dir)
    md = render_markdown(report, baseline, chart_paths)
    html = render_html(report, baseline, chart_paths, out_dir)
    paths = {"md": out_dir / f"{stem}.md", "html": out_dir / f"{stem}.html"}
    paths["md"].write_text(md, encoding="utf-8")
    paths["html"].write_text(html, encoding="utf-8")
    return paths
