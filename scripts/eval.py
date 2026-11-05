#!/usr/bin/env python3
"""CLI for running evaluations and comparing regressions."""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.eval.golden import GoldenDataset, create_default_golden_tasks
from packages.eval.runner import EvalRunner


def cmd_init(args):
    """Initialize default golden dataset."""
    dataset = create_default_golden_tasks()
    tasks = dataset.load_tasks()
    print(f"✓ Created golden dataset with {len(tasks)} tasks")
    print(f"  Location: {dataset.tasks_file}")
    for task in tasks:
        print(f"  - {task.task_id}: {task.category}")


def cmd_run(args):
    """Run evaluation on all golden tasks."""
    dataset = GoldenDataset()
    tasks = dataset.load_tasks()

    if not tasks:
        print("No golden tasks found. Run: eval init")
        sys.exit(1)

    print(f"Running {len(tasks)} golden tasks...")
    print(f"  Config: {args.config}")

    # Parse config
    config = json.loads(args.config) if args.config else {"model": "gpt-4", "version": "1.0"}

    runner = EvalRunner(max_parallel=args.max_parallel)

    # Run evaluation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    report = loop.run_until_complete(runner.run_eval(tasks, config))
    loop.close()

    # Save report
    report_file = runner.save_report(report)
    print(f"\n✓ Evaluation complete in {report.duration_seconds:.2f}s")
    print(f"  Report: {report_file}")
    print(f"  Run ID: {report.run_id}")

    # Print summary
    print(f"\nSummary:")
    print(f"  Pass Rate: {report.summary['pass_rate']:.1%}")
    print(f"  Passed: {report.summary['passed']}/{report.summary['total_tasks']}")
    print(f"  Failed: {report.summary['failed']}")
    print(f"  Errors: {report.summary['errors']}")
    print(f"  Total Cost: ${report.summary['total_cost_usd']:.4f}")
    print(f"  Avg Latency: {report.summary['avg_latency_ms']:.0f}ms")

    # Print by category
    print(f"\nBy Category:")
    for cat, stats in report.summary["by_category"].items():
        print(f"  {cat}:")
        print(f"    Pass Rate: {stats['passed']}/{stats['passed']+stats['failed']+stats['errors']}")
        print(f"    Avg Score: {stats['avg_score']:.2f}")

    # Export markdown
    if args.markdown:
        md_file = report_file.with_suffix(".md")
        md_content = runner.format_report_markdown(report)
        md_file.write_text(md_content)
        print(f"\n  Markdown: {md_file}")

    return report.run_id


def cmd_compare(args):
    """Compare two evaluation runs and detect regressions."""
    runner = EvalRunner()

    # Find runs if not specified
    run1_id = args.run1
    run2_id = args.run2

    if not run1_id:
        # Find latest run with matching config hash
        report = runner.find_latest_run(args.config_hash)
        if report:
            run1_id = report.run_id
        else:
            print("No baseline run found. Run: eval run")
            sys.exit(1)

    print(f"Comparing {run1_id} vs {run2_id}...")

    comparison = runner.compare_runs(run1_id, run2_id)

    if "error" in comparison:
        print(f"Error: {comparison['error']}")
        sys.exit(1)

    # Print results
    summary = comparison["summary"]
    print(f"\nRegression Report:")
    print(f"  Total Tasks: {summary['total_tasks']}")
    print(f"  Regressions: {summary['regressions']}")
    print(f"  Improvements: {summary['improvements']}")
    print(f"  Pass Rate Delta: {summary['pass_rate_delta']:+.1%}")
    print(f"  Cost Delta: ${summary['cost_delta_usd']:+.4f}")
    print(f"  Latency Delta: {summary['latency_delta_ms']:+.0f}ms")

    if summary["regressions"] > 0:
        print(f"\n⚠️  Regressions:")
        for reg in comparison["regressions"]:
            print(f"  - {reg['task_id']}: {reg['change']}")
            print(f"    Score: {reg['score_delta']:+.2f}")

    if summary["improvements"] > 0:
        print(f"\n✅ Improvements:")
        for imp in comparison["improvements"]:
            print(f"  - {imp['task_id']}: {imp['change']}")
            print(f"    Score: {imp['score_delta']:+.2f}")

    # Export markdown
    if args.markdown:
        results_dir = runner.results_dir
        comparison_file = results_dir / f"comparison_{run1_id}_{run2_id}.md"
        md_content = runner.format_comparison_markdown(comparison)
        comparison_file.write_text(md_content)
        print(f"\n  Report: {comparison_file}")

    # Exit with error code if regressions found
    if summary["regressions"] > 0:
        sys.exit(1)


def cmd_list(args):
    """List all evaluation runs."""
    runner = EvalRunner()
    results_dir = runner.results_dir

    if not results_dir.exists():
        print("No evaluation runs found.")
        return

    runs = sorted(results_dir.glob("eval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not runs:
        print("No evaluation runs found.")
        return

    print(f"Found {len(runs)} evaluation runs:\n")
    print(f"{'Run ID':<45} {'Pass Rate':<12} {'Cost':<12} {'Latency':<12}")
    print("-" * 81)

    for run_file in runs:
        report = runner.load_report(run_file.stem)
        if report:
            pass_rate = f"{report.summary['pass_rate']:.1%}"
            cost = f"${report.summary['total_cost_usd']:.4f}"
            latency = f"{report.summary['avg_latency_ms']:.0f}ms"
            print(f"{report.run_id:<45} {pass_rate:<12} {cost:<12} {latency:<12}")


def cmd_show(args):
    """Show details of an evaluation run."""
    runner = EvalRunner()
    report = runner.load_report(args.run_id)

    if not report:
        print(f"Run not found: {args.run_id}")
        sys.exit(1)

    # Print markdown report
    md_content = runner.format_report_markdown(report)
    print(md_content)

    # Export if requested
    if args.export:
        export_file = Path(args.export)
        export_file.write_text(md_content)
        print(f"\nExported to: {export_file}")


def main():
    parser = argparse.ArgumentParser(description="Agent evaluation framework")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    subparsers.add_parser("init", help="Initialize golden dataset")

    # run
    run_parser = subparsers.add_parser("run", help="Run evaluation")
    run_parser.add_argument("--config", help="Config JSON (default: {model: gpt-4, version: 1.0})")
    run_parser.add_argument("--max-parallel", type=int, default=4, help="Max parallel tasks")
    run_parser.add_argument("--markdown", action="store_true", help="Export markdown report")

    # compare
    compare_parser = subparsers.add_parser("compare", help="Compare two runs")
    compare_parser.add_argument("--run1", help="First run ID (default: latest)")
    compare_parser.add_argument("--run2", required=True, help="Second run ID")
    compare_parser.add_argument("--config-hash", help="Config hash for baseline (if run1 not specified)")
    compare_parser.add_argument("--markdown", action="store_true", help="Export markdown report")

    # list
    subparsers.add_parser("list", help="List all runs")

    # show
    show_parser = subparsers.add_parser("show", help="Show run details")
    show_parser.add_argument("run_id", help="Run ID")
    show_parser.add_argument("--export", help="Export to file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "init":
        cmd_init(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)


if __name__ == "__main__":
    main()
