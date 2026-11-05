"""Golden dataset builder and loader for evaluation tasks."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class GoldenTask:
    """Represents a single golden evaluation task."""
    task_id: str
    task: str
    category: str  # data_analysis | multi_hop_research | code_execution
    expected_output_schema: Dict[str, Any]
    checks: List[str]  # List of check names to run
    reference_answer: Optional[str] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GoldenDataset:
    """Manages golden dataset loading and persistence."""

    def __init__(self, dataset_dir: Path = None):
        self.dataset_dir = dataset_dir or Path(__file__).parent.parent.parent / "datasets" / "golden"
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.dataset_dir / "tasks.jsonl"

    def save_task(self, task: GoldenTask) -> None:
        """Append a task to the golden dataset."""
        with open(self.tasks_file, "a") as f:
            f.write(json.dumps(task.to_dict()) + "\n")

    def load_tasks(self) -> List[GoldenTask]:
        """Load all golden tasks from disk."""
        if not self.tasks_file.exists():
            return []

        tasks = []
        with open(self.tasks_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    tasks.append(GoldenTask(**data))
        return tasks

    def init_default_tasks(self) -> None:
        """Initialize with a set of default golden tasks across categories."""
        if self.tasks_file.exists():
            return  # Already initialized

        # DATA ANALYSIS: Fetch CSV, compute stats, generate chart
        self.save_task(GoldenTask(
            task_id="da_001",
            task="Fetch CSV from https://example.com/iris.csv, compute mean/median of sepal_length, generate a histogram, save chart to /out/histogram.png",
            category="data_analysis",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "artifacts": {"type": "array", "items": {"type": "string"}},
                    "stats": {"type": "object", "properties": {
                        "mean": {"type": "number"},
                        "median": {"type": "number"}
                    }}
                },
                "required": ["artifacts", "stats"]
            },
            checks=["schema_valid", "code_passes_tests", "numeric_tolerance"],
            reference_answer='{"mean": 5.843, "median": 5.8, "artifacts": ["histogram.png"]}'
        ))

        # DATA ANALYSIS: Multi-step data transformation
        self.save_task(GoldenTask(
            task_id="da_002",
            task="Fetch population.json, filter countries with pop > 1M, calculate regional summary stats, save results.json",
            category="data_analysis",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "object"},
                    "count": {"type": "integer"},
                    "file_generated": {"type": "boolean"}
                },
                "required": ["summary", "count", "file_generated"]
            },
            checks=["schema_valid", "numeric_tolerance", "file_exists"],
        ))

        # MULTI-HOP RESEARCH: Search → Fetch → Synthesize
        self.save_task(GoldenTask(
            task_id="mhr_001",
            task="Search for 'Claude 3.5 capabilities', fetch top 3 results, synthesize findings into a short paragraph, save to /out/summary.md",
            category="multi_hop_research",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "minLength": 100},
                    "sources_cited": {"type": "integer", "minimum": 1},
                    "artifacts": {"type": "array"}
                },
                "required": ["summary", "sources_cited", "artifacts"]
            },
            checks=["schema_valid", "citation_quality", "output_length"],
        ))

        # MULTI-HOP RESEARCH: Multi-step analysis
        self.save_task(GoldenTask(
            task_id="mhr_002",
            task="Search for 'agent-based systems benchmarks', fetch 3 papers, extract key metrics, generate a comparison table",
            category="multi_hop_research",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "metrics": {"type": "array", "items": {"type": "object"}},
                    "paper_count": {"type": "integer"},
                    "table_generated": {"type": "boolean"}
                },
                "required": ["metrics", "paper_count", "table_generated"]
            },
            checks=["schema_valid", "data_extraction_accuracy"],
        ))

        # CODE EXECUTION: Generate and test code
        self.save_task(GoldenTask(
            task_id="ce_001",
            task="Write Python code to implement Fibonacci sequence (first 20 terms), save to /out/fib.py, test correctness",
            category="code_execution",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "code_file": {"type": "string"},
                    "tests_passed": {"type": "integer"},
                    "fib_20th": {"type": "integer"}
                },
                "required": ["code_file", "tests_passed", "fib_20th"]
            },
            checks=["schema_valid", "code_passes_tests", "numeric_exact"],
            reference_answer='{"fib_20th": 6765, "tests_passed": 20}'
        ))

        # CODE EXECUTION: Sorting algorithm with test harness
        self.save_task(GoldenTask(
            task_id="ce_002",
            task="Implement quicksort, test on [3,1,4,1,5,9,2,6], verify sorted output and performance",
            category="code_execution",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "sorted": {"type": "array", "items": {"type": "integer"}},
                    "algorithm": {"type": "string"},
                    "passes": {"type": "boolean"}
                },
                "required": ["sorted", "algorithm", "passes"]
            },
            checks=["schema_valid", "code_passes_tests", "correctness_exact"],
            reference_answer='{"sorted": [1, 1, 2, 3, 4, 5, 6, 9], "passes": true}'
        ))

        # DATA ANALYSIS: Statistical analysis with visualization
        self.save_task(GoldenTask(
            task_id="da_003",
            task="Generate 1000 random samples from normal distribution (mean=100, std=15), compute quartiles, create boxplot, save analysis.json",
            category="data_analysis",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "q1": {"type": "number"},
                    "q2": {"type": "number"},
                    "q3": {"type": "number"},
                    "chart_created": {"type": "boolean"}
                },
                "required": ["q1", "q2", "q3", "chart_created"]
            },
            checks=["schema_valid", "numeric_tolerance", "quartile_order"],
        ))

        # MULTI-HOP RESEARCH: Compare multiple sources
        self.save_task(GoldenTask(
            task_id="mhr_003",
            task="Research 'machine learning performance benchmarks', fetch 2+ sources, extract benchmark scores, generate comparison",
            category="multi_hop_research",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "benchmarks": {"type": "array", "minItems": 2},
                    "best_performer": {"type": "string"},
                    "comparison_complete": {"type": "boolean"}
                },
                "required": ["benchmarks", "best_performer", "comparison_complete"]
            },
            checks=["schema_valid", "data_extraction_accuracy", "source_count"],
        ))

        # CODE EXECUTION: Data transformation and validation
        self.save_task(GoldenTask(
            task_id="ce_003",
            task="Read CSV with columns [id, name, score], filter score >= 80, write to /out/filtered.csv, validate output",
            category="code_execution",
            expected_output_schema={
                "type": "object",
                "properties": {
                    "input_rows": {"type": "integer"},
                    "output_rows": {"type": "integer"},
                    "validated": {"type": "boolean"}
                },
                "required": ["input_rows", "output_rows", "validated"]
            },
            checks=["schema_valid", "code_passes_tests", "output_file_valid"],
        ))


def create_default_golden_tasks():
    """Create and persist the default golden dataset."""
    dataset = GoldenDataset()
    dataset.init_default_tasks()
    return dataset
