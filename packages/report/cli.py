"""CLI entry point for the report generator.

Usage (``packages`` on PYTHONPATH):

    python -m report trace <run.json> --out reports/traces/
    python -m report eval <results.json> [--baseline <baseline.json>] --out reports/evals/
    python -m report build-index --out reports/

Exit codes: 0 ok, 2 bad input, 3 generation failed. No wall-clock input
ever reaches an output; running twice on the same files yields identical
bytes (charts included).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ReportError
from .eval_report import write_outputs as write_eval
from .schema import load_eval, load_trace
from .trace_report import write_outputs as write_trace


def _cmd_trace(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    for src in args.inputs:
        p = Path(src)
        trace = load_trace(p)  # raises ReportError with the field named
        paths = write_outputs(trace, p, out_dir)
        print(f"wrote {paths['md']}")
        print(f"wrote {paths['html']}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    report = load_eval(Path(args.input))
    baseline = load_eval(Path(args.baseline)) if args.baseline else None
    if baseline is not None and baseline.config_id == report.config_id:
        raise ReportError("baseline must be a different config than the report")
    paths = write_eval(report, baseline, out_dir)
    print(f"wrote {paths['md']}")
    print(f"wrote {paths['html']}")
    return 0


def _cmd_build_index(args: argparse.Namespace) -> int:
    from .index import build_index

    out = Path(args.out)
    path = build_index(out)
    print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="report", description="Agent Forge static report generator")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("trace", help="trace JSON -> Markdown + self-contained HTML")
    t.add_argument("inputs", nargs="+", metavar="run.json", help="one or more trace JSON files")
    t.add_argument("--out", default="reports/traces/", help="output directory")
    t.set_defaults(func=_cmd_trace)

    e = sub.add_parser("eval", help="eval results JSON -> Markdown + HTML + charts")
    e.add_argument("input", metavar="results.json")
    e.add_argument("--baseline", help="baseline results JSON for delta/regression callouts")
    e.add_argument("--out", default="reports/evals/", help="output directory")
    e.set_defaults(func=_cmd_eval)

    i = sub.add_parser("build-index", help="scan reports/ and write reports/index.json")
    i.add_argument("--out", default="reports/", help="reports root to scan")
    i.set_defaults(func=_cmd_build_index)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ReportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
