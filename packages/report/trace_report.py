"""Trace JSON -> Markdown + self-contained HTML.

The Markdown is GitHub-renderable: artifact images are also written next to
the report under ``assets/<stem>/`` so GitHub (which strips ``data:`` URIs)
still shows them. The HTML is a single file: inline CSS, base64 images, no
network, opens offline.

Determinism: no wall-clock input reaches the templates; everything shown
comes from the trace (timestamps, run id) plus the fixed generator version.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import GENERATOR_VERSION, SCHEMA_VERSION
from .schema import ReportError, TraceRun, TraceStep

_TPL_DIR = Path(__file__).parent / "templates"

PROMPT_TRUNCATE = 400  # chars of an llm_call prompt shown inline
_MAX_FENCE = 4000  # cap any fenced output so one report stays readable


# ---------------------------------------------------------------------------
# context building
# ---------------------------------------------------------------------------

def _esc(s: str, max_len: int = _MAX_FENCE) -> str:
    s = s or ""
    return s if len(s) <= max_len else s[:max_len] + "\n…[truncated]"


def _fenced(text: str, lang: str = "") -> str:
    """Fence text for Markdown, closing the fence safely if text contains ```."""
    fence = "````" if "```" in text else "```"
    body = text if lang == "" else f"{lang}\n{text}"
    return f"{fence}{body}\n{fence}"


def _prompt_ref(step: TraceStep) -> dict[str, str]:
    """Hash + truncated view of an llm_call prompt (input.prompt, or the whole input)."""
    raw = step.input.get("prompt")
    source = raw if isinstance(raw, str) else json.dumps(step.input, sort_keys=True, indent=2)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return {
        "hash": digest,
        "text": source[:PROMPT_TRUNCATE],
        "truncated": len(source) > PROMPT_TRUNCATE,
        "full": source,
    }


def _output_summary(step: TraceStep, max_keys: int = 4) -> str:
    """One line: the most informative keys of a tool output."""
    out = step.output or {}
    for key in ("result", "summary", "text", "answer"):
        if key in out and isinstance(out[key], (str, int, float, bool)):
            return f"{key}: {out[key]}"
    keys = sorted(out)[:max_keys]
    if not keys:
        return "no output"
    parts = [f"{k}={json.dumps(out[k], sort_keys=True)[:120]}" for k in keys]
    return ", ".join(parts)


def _code_of(step: TraceStep) -> tuple[str, str, int]:
    """(source, lang) from a code_exec step's input + exit code."""
    src = step.input.get("code") or step.input.get("python") or ""
    lang = step.input.get("language", "python")
    return src, lang, int(step.output.get("exit_code", 0))


def _artifacts_md(step: TraceStep, stem: str) -> str:
    lines = []
    for a in step.artifacts:
        path = f"assets/{stem}/{a.name}"
        if a.mime.startswith("image/"):
            lines.append(f"![{a.name}]({path})")
        else:
            lines.append(f"artifact: `{a.name}` ({a.mime}, {a.size} bytes) → {path}")
    return "\n".join(lines)


def _artifacts_html(step: TraceStep) -> str:
    out = []
    for a in step.artifacts:
        if a.mime.startswith("image/"):
            data_url = f"data:{a.mime};base64,{a.data_base64}"
            out.append(
                f'<figure class="art"><img src="{data_url}" alt="{a.name}">'
                f'<figcaption>{a.name} · {a.size} bytes</figcaption></figure>'
            )
        else:
            out.append(f'<p class="art">artifact: <code>{a.name}</code> ({a.mime})</p>')
    return "\n".join(out)


def _step_md(step: TraceStep, stem: str) -> list[str]:
    """Render one step's body (after its head line) as Markdown lines."""
    lines: list[str] = []
    if step.type == "tool_call":
        lines.append(_fenced(json.dumps(step.input, sort_keys=True, indent=2), "json"))
        lines.append(f"output — {_output_summary(step)}")
        if step.error:
            lines.append(f"error — {step.error}")
    elif step.type == "llm_call":
        ref = _prompt_ref(step)
        lines.append(f"prompt — sha256 `{ref['hash']}`" + (" (truncated)" if ref["truncated"] else ""))
        lines.append(_fenced(ref["text"], "text"))
        out_text = step.output.get("text")
        if out_text is None:
            out_text = json.dumps(step.output, sort_keys=True, indent=2)
        lines.append("output")
        lines.append(_fenced(_esc(out_text), "text"))
    elif step.type == "code_exec":
        src, lang, code = _code_of(step)
        if src:
            lines.append(_fenced(src, lang))
        out = step.output or {}
        if out.get("stdout"):
            lines.append("stdout")
            lines.append(_fenced(str(out["stdout"]), "text"))
        if out.get("stderr"):
            lines.append("stderr")
            lines.append(_fenced(str(out["stderr"]), "text"))
        if code != 0:
            lines.append(f"exit code — {code}")
        if step.artifacts:
            lines.append("artifacts")
            lines.extend(_artifacts_md(step, stem).split("\n"))
    elif step.type == "critique":
        verdict = step.verdict or step.output.get("verdict", "—")
        lines.append(f"**verdict: {verdict}**")
        score = step.output.get("score")
        if score is not None:
            lines.append(f"confidence — {score}")
        feedback = step.output.get("feedback") or step.output.get("text")
        if feedback:
            lines.append(_esc(feedback))
    elif step.type == "revision":
        text = step.output.get("revised") or step.output.get("text")
        lines.append(_fenced(_esc(text or json.dumps(step.output, sort_keys=True)), "text"))
    else:  # plan
        text = step.output.get("text") or step.output.get("plan")
        if text:
            lines.append(_esc(text if isinstance(text, str) else json.dumps(text, sort_keys=True, indent=2)))
        else:
            lines.append(_fenced(json.dumps(step.output, sort_keys=True, indent=2), "json"))
    if step.error and step.type != "tool_call":
        lines.append(f"error — {step.error}")
    return lines


def _step_head_md(step: TraceStep, depth: int) -> str:
    meta = f"step {step.step_id} · {step.type}"
    if step.name:
        meta += f" · {step.name}"
    if step.parent_step_id is not None:
        meta += f" (parent {step.parent_step_id})"
    toks = f"tokens {step.tokens.in} in / {step.tokens.out} out"
    head = f"{'  ' * (depth + 1)}- **{step.type}** — {meta} · {toks} · {step.latency_ms} ms · ${step.cost_usd:.4f}"
    return head


def _final_md(trace: TraceRun, stem: str) -> list[str]:
    lines = ["## Final output", ""]
    fo = trace.final_output or {}
    answer = fo.get("answer")
    if answer:
        lines.extend([_esc(str(answer)), ""])
    for a in fo.get("artifacts", []):
        if isinstance(a, dict) and a.get("data_base64"):
            lines.append(f"![{a.get('name')}]({f'assets/{stem}/{a.get('name')}'})")
        else:
            lines.append(f"artifact: `{a.get('name', a)}`")
    leftovers = {k: v for k, v in fo.items() if k not in ("answer", "artifacts")}
    if leftovers:
        lines.extend([_fenced(json.dumps(leftovers, sort_keys=True, indent=2), "json"), ""])
    return lines


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TPL_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _step_contexts(trace: TraceRun, stem: str) -> list[dict[str, Any]]:
    blocks = []
    for step, depth in trace.iter_tree():
        blocks.append(
            {
                "step": step,
                "depth": depth,
                "head": _step_head_md(step, depth),
                "body": _step_md(step, stem),
            }
        )
    return blocks


def render_markdown(trace: TraceRun, stem: str) -> str:
    """GitHub-renderable Markdown for one trace, from trace.md.j2."""
    total = trace.total_tokens()
    ctx = make_md_context(trace, stem)
    ctx.update(
        {
            "total_ms": _fmt_ms(trace.total_latency_ms()),
            "total_cost": trace.total_cost_usd(),
            "n_steps": len(trace.steps),
            "tok_in": total.in,
            "tok_out": total.out,
            "steps": ctx["steps"],
            "final_body": "\n".join(_final_md(trace, stem)).strip("\n"),
            "gen_version": GENERATOR_VERSION,
            "schema_version": trace.schema_version,
            "timestamp": trace.finished_at or trace.started_at or "n/a",
        }
    )
    return _env().get_template("trace.md.j2").render(**ctx)


def _fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms} ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f} s"
    return f"{ms // 60_000} m {ms % 60_000 // 1000} s"


def render_html(trace: TraceRun, stem: str) -> str:
    """Self-contained HTML: inline CSS + base64 images, works offline."""
    env = Environment(
        loader=FileSystemLoader(str(_TPL_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("trace.html.j2")
    total = trace.total_tokens()
    return tpl.render(
        trace=trace,
        stem=stem,
        total_ms=_fmt_ms(trace.total_latency_ms()),
        total_cost=f"${trace.total_cost_usd():.4f}",
        tok_in=total.in,
        tok_out=total.out,
        n_steps=len(trace.steps),
        gen_version=GENERATOR_VERSION,
        schema_version=trace.schema_version,
        timestamp=trace.finished_at or trace.started_at or "n/a",
        artifacts_html=_artifacts_html_for(trace.final_output, stem),
        final_json=json.dumps(trace.final_output, sort_keys=True, indent=2),
    )


def _artifacts_html_for(final_output: dict, stem: str) -> str:
    out = []
    for a in (final_output or {}).get("artifacts", []):
        if not isinstance(a, dict):
            out.append(f"<p class='art'>artifact: <code>{a}</code></p>")
            continue
        name = a.get("name")
        if a.get("mime", "").startswith("image/") and a.get("data_base64"):
            data_url = f"data:{a.get('mime','image/png')};base64,{a['data_base64']}"
            out.append(
                f'<figure class="art"><img src="{data_url}" alt="{name}" width="{a.get("size", 0)}">'
                f'<figcaption>{name} · {a.get("size", 0)} bytes</figcaption></figure>'
            )
        else:
            out.append(f"<p class='art'>artifact: <code>{name}</code> ({a.get('mime', '?')})</p>")
    return "\n".join(out)


def write_outputs(trace: TraceRun, src: Path, out_dir: Path) -> dict[str, Path]:
    """Write ``<stem>.md`` + ``<stem>.html`` (+ asset images) for one trace."""
    stem = src.stem
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = render_markdown(trace, stem)
    html = render_html(trace, stem)
    paths = {
        "md": out_dir / f"{stem}.md",
        "html": out_dir / f"{stem}.html",
    }
    paths["md"].write_text(md, encoding="utf-8")
    paths["html"].write_text(html, encoding="utf-8")
    # Also write artifact bytes next to the md so GitHub (which strips data:
    # URIs) still renders the images referenced by the asset links above.
    asset_dir = out_dir / "assets" / stem
    for step in trace.steps:
        for a in step.artifacts:
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_dir.joinpath(a.name).write_bytes(a.decoded_bytes())
    for a in (trace.final_output or {}).get("artifacts", []):
        if isinstance(a, dict) and a.get("data_base64"):
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_dir.joinpath(a.get("name", "unnamed")).write_bytes(
                base64.b64decode(a["data_base64"])
            )
    return paths


def make_md_context(trace: TraceRun, stem: str) -> dict[str, Any]:
    """Everything a Markdown template needs — single source for tests."""
    step_blocks: list[dict[str, Any]] = []
    for step, depth in trace.iter_tree():
        step_blocks.append(
            {
                "step": step,
                "depth": depth,
                "head": _step_head_md(step, depth),
                "body": _step_md(step, stem),
            }
        )
    return {
        "trace": trace,
        "stem": stem,
        "steps": step_blocks,
        "total_ms": _fmt_ms(trace.total_latency_ms()),
        "total_cost": trace.total_cost_usd(),
        "n_steps": len(trace.steps),
    }
