"""Deterministic and LLM-based scorers for evaluating agent outputs."""
import json
import re
from typing import Any, Callable, Dict, Optional, Tuple
from dataclasses import dataclass
from jsonschema import validate, ValidationError
from pathlib import Path


@dataclass
class ScorerResult:
    """Result of scoring a single task output."""
    task_id: str
    scorer_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str
    error: Optional[str] = None


class DeterministicScorer:
    """Base class for deterministic scorers."""

    def score(self, output: Any, reference: Any, **kwargs) -> ScorerResult:
        raise NotImplementedError


class SchemaValidator(DeterministicScorer):
    """Validates output against JSON schema."""

    def score(self, output: Any, reference: Any, task_id: str = "", schema: Dict = None, **kwargs) -> ScorerResult:
        if schema is None:
            return ScorerResult(task_id, "schema_valid", False, 0.0, "No schema provided")

        try:
            # Parse if string
            if isinstance(output, str):
                output = json.loads(output)
            validate(instance=output, schema=schema)
            return ScorerResult(task_id, "schema_valid", True, 1.0, "Schema validation passed")
        except ValidationError as e:
            return ScorerResult(task_id, "schema_valid", False, 0.0, f"Schema validation failed: {e.message}")
        except json.JSONDecodeError as e:
            return ScorerResult(task_id, "schema_valid", False, 0.0, f"Invalid JSON: {e}")
        except Exception as e:
            return ScorerResult(task_id, "schema_valid", False, 0.0, f"Error: {str(e)}", error=str(e))


class NumericTolerance(DeterministicScorer):
    """Validates numeric values within tolerance (default ±5%)."""

    def score(self, output: Any, reference: Any, task_id: str = "", tolerance: float = 0.05, **kwargs) -> ScorerResult:
        if reference is None:
            return ScorerResult(task_id, "numeric_tolerance", False, 0.0, "No reference value provided")

        try:
            if isinstance(output, str):
                output = json.loads(output)

            # Extract numeric values from both output and reference
            output_nums = self._extract_numbers(output)
            ref_nums = self._extract_numbers(reference)

            if not ref_nums:
                return ScorerResult(task_id, "numeric_tolerance", False, 0.0, "No numeric values in reference")

            if not output_nums:
                return ScorerResult(task_id, "numeric_tolerance", False, 0.0, "No numeric values in output")

            # Compare each reference number with closest output number
            matches = 0
            for ref_val in ref_nums:
                for out_val in output_nums:
                    if abs(out_val - ref_val) / max(abs(ref_val), 1e-10) <= tolerance:
                        matches += 1
                        break

            score = matches / len(ref_nums)
            passed = score >= 0.8  # 80% of values must match
            return ScorerResult(task_id, "numeric_tolerance", passed, score, f"Numeric match: {matches}/{len(ref_nums)}")
        except Exception as e:
            return ScorerResult(task_id, "numeric_tolerance", False, 0.0, f"Error: {str(e)}", error=str(e))

    @staticmethod
    def _extract_numbers(obj: Any) -> list:
        """Recursively extract all numeric values from an object."""
        numbers = []
        if isinstance(obj, (int, float)):
            numbers.append(float(obj))
        elif isinstance(obj, str):
            # Try to extract from string
            matches = re.findall(r'-?\d+\.?\d*', obj)
            numbers.extend([float(m) for m in matches if m])
        elif isinstance(obj, dict):
            for v in obj.values():
                numbers.extend(NumericTolerance._extract_numbers(v))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                numbers.extend(NumericTolerance._extract_numbers(item))
        return numbers


class ExactMatch(DeterministicScorer):
    """Exact match scorer for string/structured data."""

    def score(self, output: Any, reference: Any, task_id: str = "", **kwargs) -> ScorerResult:
        if reference is None:
            return ScorerResult(task_id, "exact_match", False, 0.0, "No reference provided")

        try:
            if isinstance(output, str) and isinstance(reference, str):
                match = output.strip() == reference.strip()
            else:
                if isinstance(output, str):
                    output = json.loads(output)
                if isinstance(reference, str):
                    reference = json.loads(reference)
                match = output == reference

            score = 1.0 if match else 0.0
            return ScorerResult(task_id, "exact_match", match, score, "Exact match" if match else "Mismatch")
        except Exception as e:
            return ScorerResult(task_id, "exact_match", False, 0.0, f"Error: {str(e)}", error=str(e))


class CodeTestPass(DeterministicScorer):
    """Verifies generated code passes tests (checks for test_results in output)."""

    def score(self, output: Any, reference: Any, task_id: str = "", **kwargs) -> ScorerResult:
        try:
            if isinstance(output, str):
                output = json.loads(output)

            if isinstance(output, dict) and "test_results" in output:
                results = output["test_results"]
                if isinstance(results, dict):
                    passed = results.get("passed", 0)
                    total = results.get("total", 0)
                    if total > 0:
                        score = passed / total
                        return ScorerResult(task_id, "code_passes_tests", score >= 0.8, score, f"Tests: {passed}/{total}")

            return ScorerResult(task_id, "code_passes_tests", False, 0.0, "No test results in output")
        except Exception as e:
            return ScorerResult(task_id, "code_passes_tests", False, 0.0, f"Error: {str(e)}", error=str(e))


class FileExists(DeterministicScorer):
    """Checks if expected files were generated."""

    def score(self, output: Any, reference: Any, task_id: str = "", expected_files: list = None, **kwargs) -> ScorerResult:
        if not expected_files:
            expected_files = ["result.json", "output.csv", "chart.png"]

        try:
            if isinstance(output, str):
                output = json.loads(output)

            files_found = []
            if isinstance(output, dict) and "artifacts" in output:
                files_found = output["artifacts"]

            # Check if expected files are in the list
            found_count = sum(1 for f in expected_files if any(f in str(af) for af in files_found))
            score = found_count / len(expected_files) if expected_files else 0.0

            return ScorerResult(task_id, "file_exists", score >= 0.5, score, f"Files found: {found_count}/{len(expected_files)}")
        except Exception as e:
            return ScorerResult(task_id, "file_exists", False, 0.0, f"Error: {str(e)}", error=str(e))


class CitationQuality(DeterministicScorer):
    """Checks for proper citations in research outputs."""

    def score(self, output: Any, reference: Any, task_id: str = "", **kwargs) -> ScorerResult:
        try:
            if isinstance(output, str):
                text = output
            elif isinstance(output, dict):
                text = output.get("summary", "") or output.get("output", "")
            else:
                text = str(output)

            # Look for URL citations or reference markers
            url_pattern = r'https?://\S+'
            refs_pattern = r'\[[\d\w\s,]+\]'

            urls = re.findall(url_pattern, text)
            refs = re.findall(refs_pattern, text)

            has_citations = len(urls) >= 1 or len(refs) >= 2
            score = 1.0 if has_citations else 0.5
            citation_count = len(urls) + len(refs)

            return ScorerResult(task_id, "citation_quality", has_citations, score, f"Citations found: {citation_count}")
        except Exception as e:
            return ScorerResult(task_id, "citation_quality", False, 0.0, f"Error: {str(e)}", error=str(e))


class OutputLength(DeterministicScorer):
    """Validates output meets minimum length requirements."""

    def score(self, output: Any, reference: Any, task_id: str = "", min_length: int = 100, **kwargs) -> ScorerResult:
        try:
            if isinstance(output, dict):
                text = output.get("summary") or output.get("output") or json.dumps(output)
            else:
                text = str(output)

            length = len(text)
            passed = length >= min_length
            score = min(length / max(min_length * 2, 1), 1.0)  # Scale up to 2x min_length

            return ScorerResult(task_id, "output_length", passed, score, f"Length: {length} chars (min: {min_length})")
        except Exception as e:
            return ScorerResult(task_id, "output_length", False, 0.0, f"Error: {str(e)}", error=str(e))


class ScorerRegistry:
    """Registry of all available scorers."""

    def __init__(self):
        self.scorers: Dict[str, Callable] = {
            "schema_valid": SchemaValidator().score,
            "numeric_tolerance": NumericTolerance().score,
            "exact_match": ExactMatch().score,
            "code_passes_tests": CodeTestPass().score,
            "file_exists": FileExists().score,
            "citation_quality": CitationQuality().score,
            "output_length": OutputLength().score,
        }

    def register(self, name: str, scorer: Callable):
        """Register a custom scorer."""
        self.scorers[name] = scorer

    def score(self, check_name: str, output: Any, reference: Any, **kwargs) -> ScorerResult:
        """Run a named scorer."""
        if check_name not in self.scorers:
            return ScorerResult(
                kwargs.get("task_id", ""),
                check_name,
                False,
                0.0,
                f"Unknown scorer: {check_name}"
            )

        try:
            return self.scorers[check_name](output, reference, **kwargs)
        except Exception as e:
            return ScorerResult(
                kwargs.get("task_id", ""),
                check_name,
                False,
                0.0,
                f"Scorer error: {str(e)}",
                error=str(e)
            )


# Global registry
scorer_registry = ScorerRegistry()


# Alias for common check names (map to actual scorer implementations)
CHECK_ALIASES = {
    "correctness_exact": "exact_match",
    "code_correctness": "code_passes_tests",
    "numeric_exact": "exact_match",
    "quartile_order": "numeric_tolerance",
    "source_count": "file_exists",
    "data_extraction_accuracy": "numeric_tolerance",
    "output_file_valid": "file_exists",
}


def run_checks(task_id: str, output: Any, expected_schema: Dict, checks: list, reference_answer: Optional[str] = None) -> Tuple[float, list]:
    """Run all checks for a task, return aggregate score and detailed results."""
    results = []

    # Always run schema validation first
    schema_result = scorer_registry.score("schema_valid", output, reference_answer, task_id=task_id, schema=expected_schema)
    results.append(schema_result)

    # Run specific checks
    for check in checks:
        check_name = CHECK_ALIASES.get(check, check)
        result = scorer_registry.score(check_name, output, reference_answer, task_id=task_id)
        results.append(result)

    # Aggregate: pass if schema valid AND 80% of other checks pass
    passed_checks = sum(1 for r in results[1:] if r.passed)
    total_checks = len(results) - 1  # Exclude schema

    overall_score = (results[0].score + (passed_checks / max(total_checks, 1))) / 2 if total_checks > 0 else results[0].score
    overall_passed = results[0].passed and (passed_checks / max(total_checks, 1) >= 0.8)

    return overall_score, results
