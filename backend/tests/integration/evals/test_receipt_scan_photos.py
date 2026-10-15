"""End-to-end receipt-scan evals on real, redacted receipt photos (image in, scored items out).

Calls the real scan service in both OCR modes, so it costs money (and, for Textract, needs
AWS credentials plus a scratch bucket). It runs only from the manually dispatched LLM-eval
workflow, never in `make test-backend`. The hard- and soft-gate steps each run this module in
their own process; with GLEAN_EVAL_SCAN_CACHE set they share one set of scans and one report.
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glean.llm import Feature, LLMModelPolicy, LLMRouter
from glean.receipts import service

from .conftest import _eval_model_id_for
from .receipt_photos import (
    OCR_MODES,
    PhotoCase,
    PhotoRun,
    load_photo_cases,
    render_report,
    scan_once,
    score_scan,
    textract_configuration,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic import SecretStr

FEATURE = Feature.RECEIPT_SCAN

REPORT_PATH = Path(os.environ.get("GLEAN_EVAL_REPORT_DIR", "results")) / "receipt-photo-eval.md"
_CACHE_DIR = Path(os.environ["GLEAN_EVAL_SCAN_CACHE"]) if os.environ.get("GLEAN_EVAL_SCAN_CACHE") else None
CASES = load_photo_cases()
_EXPECTED = {case.case_id: case.expected for case in CASES}

_RUNS: list[PhotoRun] = []
_MODEL_USED: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _write_report() -> Iterator[None]:
    yield
    # Only the process that actually scanned writes the report, so a later gate never overwrites it.
    if _RUNS:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        configured = textract_configuration(os.environ) is not None
        report = render_report(_MODEL_USED[0], _RUNS, textract_configured=configured)
        REPORT_PATH.write_text(report)
        print("\n" + report)  # noqa: T201 - the workflow log is where the run's scores are read


@pytest.fixture(scope="module")
def photo_router(openrouter_api_key: SecretStr) -> LLMRouter:
    """A router whose receipt-scan model is the one the eval run chose (GLEAN_EVAL_MODEL, else production)."""
    base = LLMRouter(api_key=openrouter_api_key)
    model_id = _eval_model_id_for(FEATURE, base)
    _MODEL_USED.append(model_id)
    policy = LLMModelPolicy(production_model=model_id, eval_model=model_id)
    return LLMRouter(api_key=openrouter_api_key, policy_overrides={FEATURE: policy})


@pytest.fixture(scope="module", params=OCR_MODES)
def runs(request: pytest.FixtureRequest, photo_router: LLMRouter) -> list[PhotoRun]:
    mode: str = request.param
    try:
        bucket = textract_configuration(os.environ)
    except ValueError as exc:
        pytest.fail(str(exc), pytrace=False)
    if mode == "textract" and bucket is None:
        pytest.skip("textract: not configured (set GLEAN_EVAL_S3_BUCKET and GLEAN_EVAL_AWS_ROLE_ARN)")
    model_id = _MODEL_USED[0]
    results, fresh = scan_once(
        _CACHE_DIR, mode, model_id, lambda: [_scan_case(case, mode, photo_router, bucket or "") for case in CASES]
    )
    for run in results:
        if run.response is not None:
            run.score = score_scan(_EXPECTED[run.case_id], run.response)
    if fresh:
        _RUNS.extend(results)
    return results


def _scan_case(case: PhotoCase, mode: str, router: LLMRouter, bucket: str) -> PhotoRun:
    started = time.perf_counter()
    try:
        response = service.scan_receipt(
            case.image_path.read_bytes(),
            ocr_mode=mode,
            llm_router=router,
            aws_region=os.environ.get("AWS_REGION", "eu-west-2"),
            s3_bucket=bucket,
        )
    except Exception as exc:
        return PhotoRun(case.case_id, mode, time.perf_counter() - started, error=f"{type(exc).__name__}: {exc}"[:120])
    return PhotoRun(case.case_id, mode, time.perf_counter() - started, response)


class TestReceiptScanPhotosStructural:
    """Hard gate: every photo goes through the full scan path and comes back as items."""

    def test_every_photo_scans_to_at_least_one_item(self, runs: list[PhotoRun]) -> None:
        failures = [f"{r.case_id}: {r.error or 'no items'}" for r in runs if r.response is None or not r.response.items]
        assert not failures, "Scan failures:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestReceiptScanPhotosQuality:
    """Soft gate: advisory thresholds on the scores; the per-case table is the real output."""

    def _mean(self, runs: list[PhotoRun], field: str) -> float | None:
        values = [getattr(r.score, field) for r in runs if r.score is not None]
        values = [v for v in values if v is not None]
        return statistics.mean(values) if values else None

    @pytest.mark.parametrize(("field", "floor"), [("recall", 0.7), ("price_accuracy", 0.6), ("non_food_dropped", 0.5)])
    def test_mean_score_meets_floor(self, runs: list[PhotoRun], field: str, floor: float) -> None:
        mean = self._mean(runs, field)
        assert mean is not None, f"no {field} scores recorded"
        assert mean >= floor, f"mean {field} {mean:.0%} below {floor:.0%}"
