#!/usr/bin/env python3
"""Demo: Run evaluation scenarios showing improvement and regression."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.eval.golden import GoldenDataset
from packages.eval.runner import EvalRunner
import asyncio
import json


async def demo_regression():
    """Demo showing regression detection between two versions."""
    dataset = GoldenDataset()
    tasks = dataset.load_tasks()
    runner = EvalRunner()

    print("=" * 80)
    print("EVALUATION FRAMEWORK DEMO: Regression Detection")
    print("=" * 80)

    # Run baseline
    print("\n[1/3] Running baseline (v1.0)...")
    config_v1 = {"model": "gpt-4", "version": "1.0", "temperature": 0.7}
    report_v1 = await runner.run_eval(tasks, config_v1)
    runner.save_report(report_v1)
    print(f"✓ Baseline complete: {report_v1.run_id}")
    print(f"  Pass Rate: {report_v1.summary['pass_rate']:.1%}")
    print(f"  Passed: {report_v1.summary['passed']}/{report_v1.summary['total_tasks']}")

    # Run v2
    print("\n[2/3] Running v2.0...")
    config_v2 = {"model": "claude-opus", "version": "2.0", "temperature": 0.5}
    report_v2 = await runner.run_eval(tasks, config_v2)
    runner.save_report(report_v2)
    print(f"✓ v2.0 complete: {report_v2.run_id}")
    print(f"  Pass Rate: {report_v2.summary['pass_rate']:.1%}")
    print(f"  Passed: {report_v2.summary['passed']}/{report_v2.summary['total_tasks']}")

    # Compare
    print("\n[3/3] Comparing runs for regressions...")
    comparison = runner.compare_runs(report_v1.run_id, report_v2.run_id)

    print("\n" + "-" * 80)
    print("REGRESSION ANALYSIS")
    print("-" * 80)

    summary = comparison["summary"]
    print(f"\nMetrics:")
    print(f"  Total Tasks: {summary['total_tasks']}")
    print(f"  Pass Rate Change: {summary['pass_rate_delta']:+.1%}")
    print(f"  Cost Change: ${summary['cost_delta_usd']:+.4f}")
    print(f"  Latency Change: {summary['latency_delta_ms']:+.0f}ms")

    if summary["regressions"] > 0:
        print(f"\n⚠️  REGRESSIONS ({len(comparison['regressions'])}):")
        for reg in comparison["regressions"]:
            print(f"  ❌ {reg['task_id']}: {reg['change']}")
            print(f"     Score delta: {reg['score_delta']:+.2f}")

    if summary["improvements"] > 0:
        print(f"\n✅ IMPROVEMENTS ({len(comparison['improvements'])}):")
        for imp in comparison["improvements"]:
            print(f"  ✓ {imp['task_id']}: {imp['change']}")
            print(f"    Score delta: {imp['score_delta']:+.2f}")

    # Export comparison
    md_file = runner.results_dir / f"comparison_{report_v1.run_id}_{report_v2.run_id}.md"
    md_content = runner.format_comparison_markdown(comparison)
    md_file.write_text(md_content)
    print(f"\n📊 Reports saved to:")
    print(f"  {report_v1.run_id}.json")
    print(f"  {report_v2.run_id}.json")
    print(f"  comparison_{report_v1.run_id[:12]}..._{report_v2.run_id[:12]}....md")

    print("\n" + "=" * 80)
    print("✓ Demo complete")
    print("=" * 80)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(demo_regression())
    loop.close()
