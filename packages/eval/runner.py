"""Evaluation runner for executing golden tasks against agent configurations."""
import asyncio
import json
import hashlib
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import sys


@dataclass
class TaskResult:
    """Result of running a single task."""
    task_id: str
    task: str
    category: str
    status: str  # "PASS" | "FAIL" | "ERROR"
    score: float
    details: List[Dict[str, Any]]
    cost_usd: float
    latency_ms: float
    error: Optional[str] = None
    output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalRunReport:
    """Complete evaluation run report."""
    run_id: str
    config_hash: str
    config: Dict[str, Any]
    timestamp: str
    duration_seconds: float
    results: List[TaskResult]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config_hash": self.config_hash,
            "config": self.config,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class EvalRunner:
    """Executes evaluation tasks in parallel and produces reports."""

    def __init__(self, results_dir: Path = None, max_parallel: int = 4):
        self.results_dir = results_dir or Path(__file__).parent.parent.parent / "data" / "eval_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.max_parallel = max_parallel

    def compute_config_hash(self, config: Dict[str, Any]) -> str:
        """Hash a configuration dict for reproducible identification."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:8]

    async def run_task(self, task: Any, task_index: int, semaphore: asyncio.Semaphore) -> TaskResult:
        """Execute a single task with resource limiting."""
        async with semaphore:
            start_time = time.time()
            try:
                # Simulate task execution with varied results for demo
                await asyncio.sleep(0.1 + task_index * 0.05)

                # Create realistic mock outputs based on task category
                if task.category == "data_analysis":
                    # Data analysis: sometimes passes with stats
                    output = {
                        "status": "success",
                        "stats": {"mean": 5.843, "median": 5.8},
                        "artifacts": ["histogram.png"],
                        "test_results": {"passed": 3, "total": 3}
                    }
                elif task.category == "multi_hop_research":
                    # Research: varied completion
                    output = {
                        "status": "success",
                        "summary": "This is a detailed research summary with proper citations and sources mentioned throughout the analysis.",
                        "sources_cited": 3,
                        "artifacts": ["summary.md"]
                    }
                else:  # code_execution
                    # Code: some pass tests, some don't
                    output = {
                        "status": "success",
                        "code_file": "script.py",
                        "test_results": {"passed": 2, "total": 3},
                        "sorted": [1, 1, 2, 3, 4, 5, 6, 9],
                        "fib_20th": 6765
                    }

                # Run checks
                from .scorers import run_checks
                score, check_results = run_checks(
                    task.task_id,
                    output,
                    task.expected_output_schema,
                    task.checks,
                    task.reference_answer
                )

                latency_ms = (time.time() - start_time) * 1000
                return TaskResult(
                    task_id=task.task_id,
                    task=task.task,
                    category=task.category,
                    status="PASS" if score >= 0.8 else "FAIL",
                    score=score,
                    details=[
                        {
                            "scorer": r.scorer_name,
                            "passed": r.passed,
                            "score": r.score,
                            "details": r.details
                        }
                        for r in check_results
                    ],
                    cost_usd=0.001 * (task_index + 1),
                    latency_ms=latency_ms,
                    output=json.dumps(output)
                )
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                return TaskResult(
                    task_id=task.task_id,
                    task=task.task,
                    category=task.category,
                    status="ERROR",
                    score=0.0,
                    details=[],
                    cost_usd=0.0,
                    latency_ms=latency_ms,
                    error=str(e)
                )

    async def run_eval(self, tasks: List[Any], config: Dict[str, Any]) -> EvalRunReport:
        """Run all tasks concurrently and generate report."""
        start_time = time.time()
        config_hash = self.compute_config_hash(config)
        run_id = f"eval_{config_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Execute tasks in parallel with semaphore limit
        semaphore = asyncio.Semaphore(self.max_parallel)
        tasks_coro = [
            self.run_task(task, i, semaphore)
            for i, task in enumerate(tasks)
        ]

        results = await asyncio.gather(*tasks_coro, return_exceptions=False)

        # Compute summary
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")

        by_category = {}
        for r in results:
            cat = r.category
            if cat not in by_category:
                by_category[cat] = {"passed": 0, "failed": 0, "errors": 0, "scores": []}
            by_category[cat]["passed" if r.status == "PASS" else "failed" if r.status == "FAIL" else "errors"] += 1
            by_category[cat]["scores"].append(r.score)

        duration_seconds = time.time() - start_time

        summary = {
            "total_tasks": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / len(results) if results else 0.0,
            "avg_cost_usd": sum(r.cost_usd for r in results) / len(results) if results else 0.0,
            "total_cost_usd": sum(r.cost_usd for r in results),
            "avg_latency_ms": sum(r.latency_ms for r in results) / len(results) if results else 0.0,
            "by_category": {
                cat: {
                    "passed": v["passed"],
                    "failed": v["failed"],
                    "errors": v["errors"],
                    "avg_score": sum(v["scores"]) / len(v["scores"]) if v["scores"] else 0.0,
                }
                for cat, v in by_category.items()
            }
        }

        report = EvalRunReport(
            run_id=run_id,
            config_hash=config_hash,
            config=config,
            timestamp=datetime.utcnow().isoformat(),
            duration_seconds=duration_seconds,
            results=results,
            summary=summary
        )

        return report

    def save_report(self, report: EvalRunReport) -> Path:
        """Save report to disk."""
        report_file = self.results_dir / f"{report.run_id}.json"
        with open(report_file, "w") as f:
            f.write(report.to_json())
        return report_file

    def load_report(self, run_id: str) -> Optional[EvalRunReport]:
        """Load a previously saved report."""
        report_file = self.results_dir / f"{run_id}.json"
        if not report_file.exists():
            return None

        with open(report_file, "r") as f:
            data = json.load(f)

        results = [TaskResult(**r) for r in data["results"]]
        return EvalRunReport(
            run_id=data["run_id"],
            config_hash=data["config_hash"],
            config=data["config"],
            timestamp=data["timestamp"],
            duration_seconds=data["duration_seconds"],
            results=results,
            summary=data["summary"]
        )

    def find_latest_run(self, config_hash: str = None) -> Optional[EvalRunReport]:
        """Find the most recent evaluation run."""
        runs = sorted(self.results_dir.glob("eval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        for run_file in runs:
            if config_hash is None:
                return self.load_report(run_file.stem)

            with open(run_file) as f:
                data = json.load(f)
                if data.get("config_hash") == config_hash:
                    return self.load_report(run_file.stem)

        return None

    def compare_runs(self, run1_id: str, run2_id: str) -> Dict[str, Any]:
        """Compare two evaluation runs and detect regressions."""
        report1 = self.load_report(run1_id)
        report2 = self.load_report(run2_id)

        if not report1 or not report2:
            return {"error": "One or both reports not found"}

        # Index results by task_id
        results1 = {r.task_id: r for r in report1.results}
        results2 = {r.task_id: r for r in report2.results}

        regressions = []
        improvements = []
        unchanged = []

        all_task_ids = set(results1.keys()) | set(results2.keys())

        for task_id in all_task_ids:
            r1 = results1.get(task_id)
            r2 = results2.get(task_id)

            if r1 and r2:
                if r1.status == "PASS" and r2.status != "PASS":
                    regressions.append({
                        "task_id": task_id,
                        "change": f"PASS → {r2.status}",
                        "score_delta": r2.score - r1.score,
                        "latency_delta_ms": r2.latency_ms - r1.latency_ms,
                    })
                elif r1.status != "PASS" and r2.status == "PASS":
                    improvements.append({
                        "task_id": task_id,
                        "change": f"{r1.status} → PASS",
                        "score_delta": r2.score - r1.score,
                        "latency_delta_ms": r2.latency_ms - r1.latency_ms,
                    })
                elif r1.score != r2.score:
                    unchanged.append({
                        "task_id": task_id,
                        "score_delta": r2.score - r1.score,
                    })

        return {
            "run1": run1_id,
            "run2": run2_id,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_tasks": len(all_task_ids),
                "regressions": len(regressions),
                "improvements": len(improvements),
                "pass_rate_delta": report2.summary["pass_rate"] - report1.summary["pass_rate"],
                "cost_delta_usd": report2.summary["total_cost_usd"] - report1.summary["total_cost_usd"],
                "latency_delta_ms": report2.summary["avg_latency_ms"] - report1.summary["avg_latency_ms"],
            },
            "regressions": regressions,
            "improvements": improvements,
            "unchanged": unchanged,
        }

    def format_report_markdown(self, report: EvalRunReport) -> str:
        """Format a report as markdown."""
        lines = [
            f"# Evaluation Report: {report.run_id}",
            "",
            f"**Config**: {report.config}",
            f"**Duration**: {report.duration_seconds:.2f}s",
            f"**Timestamp**: {report.timestamp}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Pass Rate | {report.summary['pass_rate']:.1%} |",
            f"| Total Cost | ${report.summary['total_cost_usd']:.4f} |",
            f"| Avg Latency | {report.summary['avg_latency_ms']:.0f}ms |",
            "",
            "## By Category",
            "",
        ]

        for cat, stats in report.summary["by_category"].items():
            lines.append(f"### {cat}")
            lines.append("")
            lines.append(f"- Passed: {stats['passed']}")
            lines.append(f"- Failed: {stats['failed']}")
            lines.append(f"- Errors: {stats['errors']}")
            lines.append(f"- Avg Score: {stats['avg_score']:.2f}")
            lines.append("")

        lines.append("## Task Results")
        lines.append("")
        lines.append(f"| Task ID | Status | Score | Category |")
        lines.append(f"|---------|--------|-------|----------|")

        for result in report.results:
            lines.append(f"| {result.task_id} | {result.status} | {result.score:.2f} | {result.category} |")

        return "\n".join(lines)

    def format_comparison_markdown(self, comparison: Dict[str, Any]) -> str:
        """Format a comparison as markdown."""
        lines = [
            f"# Regression Report",
            "",
            f"**Runs**: {comparison['run1']} vs {comparison['run2']}",
            f"**Timestamp**: {comparison['timestamp']}",
            "",
            "## Summary",
            "",
            f"| Metric | Delta |",
            f"|--------|-------|",
            f"| Pass Rate | {comparison['summary']['pass_rate_delta']:+.1%} |",
            f"| Total Cost | ${comparison['summary']['cost_delta_usd']:+.4f} |",
            f"| Avg Latency | {comparison['summary']['latency_delta_ms']:+.0f}ms |",
            "",
        ]

        if comparison["summary"]["regressions"] > 0:
            lines.append(f"## ⚠️  Regressions ({len(comparison['regressions'])})")
            lines.append("")
            for reg in comparison["regressions"]:
                lines.append(f"- **{reg['task_id']}**: {reg['change']}")
                lines.append(f"  - Score delta: {reg['score_delta']:+.2f}")
            lines.append("")

        if comparison["summary"]["improvements"] > 0:
            lines.append(f"## ✅ Improvements ({len(comparison['improvements'])})")
            lines.append("")
            for imp in comparison["improvements"]:
                lines.append(f"- **{imp['task_id']}**: {imp['change']}")
                lines.append(f"  - Score delta: {imp['score_delta']:+.2f}")
            lines.append("")

        return "\n".join(lines)
