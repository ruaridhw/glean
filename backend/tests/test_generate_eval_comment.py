from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is not a package — add it to sys.path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_eval_comment import EvalResult, classify_results, generate_comment


class TestGenerateEvalComment:
    def test_classify_receipt_structural(self) -> None:
        results = [
            EvalResult(
                name="test_valid_json",
                classname="tests.integration.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=True,
            ),
        ]
        features = classify_results(results)
        assert len(features["receipt-scan"].structural) == 1
        assert features["receipt-scan"].structural[0].passed

    def test_classify_meal_plan_generation_heuristic(self) -> None:
        results = [
            EvalResult(
                name="test_missing_ingredients_not_in_pantry",
                classname="tests.integration.evals.test_meal_plan_generation.TestMealPlanGenerationHeuristic",
                passed=False,
                failure_message="rice was in pantry",
            ),
        ]
        features = classify_results(results)
        assert len(features["meal-plan-generation"].heuristic) == 1
        assert not features["meal-plan-generation"].heuristic[0].passed

    def test_generate_comment_has_summary_table(self) -> None:
        hard = [
            EvalResult(
                name="test_valid_json",
                classname="tests.integration.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=True,
            ),
        ]
        soft = [
            EvalResult(
                name="test_names_lowercase",
                classname="tests.integration.evals.test_receipt_scan.TestReceiptScanHeuristic",
                passed=True,
            ),
        ]
        comment = generate_comment(hard, soft, "google/gemma-3")
        assert "Eval Results" in comment
        assert "google/gemma-3" in comment
        assert "| receipt-scan" in comment
        assert "Hard gate:" in comment

    def test_generate_comment_hard_gate_failure(self) -> None:
        hard = [
            EvalResult(
                name="test_valid_json",
                classname="tests.integration.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=False,
                failure_message="Expected list, got str",
            ),
        ]
        comment = generate_comment(hard, [], "google/gemma-3")
        assert "Failed" in comment
