from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glean.receipts.schemas import ParsedIngredient, ScanResponse
from tests.integration.evals.receipt_photos import PhotoRun, render_report, scan_once, textract_configuration

if TYPE_CHECKING:
    from pathlib import Path


def _run(case_id: str = "meal-deal/photo", mode: str = "vision", seconds: float = 2.0) -> PhotoRun:
    item = ParsedIngredient(name="berry juice", quantity=330, unit="ml", unit_price=0.004, confidence=0.9)
    return PhotoRun(case_id, mode, seconds, ScanResponse(items=[item]))


class TestScanOnce:
    def test_a_second_gate_reuses_the_scans_of_the_first(self, tmp_path: Path) -> None:
        paid_scans: list[str] = []

        def scan() -> list[PhotoRun]:
            paid_scans.append("scan")
            return [_run(seconds=3.5)]

        first, first_was_fresh = scan_once(tmp_path, "vision", "model/a", scan)
        second, second_was_fresh = scan_once(tmp_path, "vision", "model/a", scan)

        assert len(paid_scans) == 1
        assert (first_was_fresh, second_was_fresh) == (True, False)
        assert second[0].response == first[0].response
        assert second[0].seconds == 3.5

    def test_a_different_model_or_mode_scans_again(self, tmp_path: Path) -> None:
        scans: list[str] = []

        def scan() -> list[PhotoRun]:
            scans.append("scan")
            return [_run()]

        scan_once(tmp_path, "vision", "model/a", scan)
        scan_once(tmp_path, "vision", "model/b", scan)
        scan_once(tmp_path, "textract", "model/b", scan)

        assert len(scans) == 3

    def test_without_a_cache_directory_every_call_scans(self) -> None:
        scans: list[str] = []

        def scan() -> list[PhotoRun]:
            scans.append("scan")
            return [_run()]

        scan_once(None, "vision", "model/a", scan)
        scan_once(None, "vision", "model/a", scan)

        assert len(scans) == 2

    def test_a_failed_scan_is_cached_with_its_error(self, tmp_path: Path) -> None:
        failed = PhotoRun("meal-deal/photo", "vision", 1.0, None, error="TimeoutError: slow")

        scan_once(tmp_path, "vision", "model/a", lambda: [failed])
        again, _ = scan_once(tmp_path, "vision", "model/a", list)

        assert (again[0].response, again[0].error) == (None, "TimeoutError: slow")


class TestTextractConfiguration:
    def test_neither_variable_set_means_not_configured(self) -> None:
        assert textract_configuration({"GLEAN_EVAL_S3_BUCKET": "", "GLEAN_EVAL_AWS_ROLE_ARN": ""}) is None
        assert textract_configuration({}) is None

    def test_both_variables_set_returns_the_scratch_bucket(self) -> None:
        env = {"GLEAN_EVAL_S3_BUCKET": "scratch-bucket", "GLEAN_EVAL_AWS_ROLE_ARN": "arn:aws:iam::1:role/eval"}

        assert textract_configuration(env) == "scratch-bucket"

    @pytest.mark.parametrize("only", ["GLEAN_EVAL_S3_BUCKET", "GLEAN_EVAL_AWS_ROLE_ARN"])
    def test_only_one_variable_set_is_an_error_naming_the_missing_one(self, only: str) -> None:
        missing = ({"GLEAN_EVAL_S3_BUCKET", "GLEAN_EVAL_AWS_ROLE_ARN"} - {only}).pop()

        with pytest.raises(ValueError, match=missing):
            textract_configuration({only: "set"})


class TestRenderReport:
    def test_an_unconfigured_textract_is_called_out_at_the_top(self) -> None:
        report = render_report("model/a", [_run()], textract_configured=False)

        assert report.splitlines()[2].startswith("**textract: not configured**")
        assert "GLEAN_EVAL_S3_BUCKET" in report
        assert "GLEAN_EVAL_AWS_ROLE_ARN" in report

    def test_a_configured_run_has_no_warning_and_lists_latency_per_case(self) -> None:
        report = render_report(
            "model/a", [_run(seconds=2.0), _run(mode="textract", seconds=7.25)], textract_configured=True
        )

        assert "not configured" not in report
        assert "meal-deal/photo" in report
        assert "7.2s" in report or "7.3s" in report
