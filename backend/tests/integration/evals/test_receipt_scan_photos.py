"""End-to-end receipt-scan evals on real, redacted receipt photos (image in, scored items out).

Calls the real scan service in both OCR modes, so it costs money (and, for Textract, needs
AWS credentials plus a scratch bucket). It runs only from the manually dispatched LLM-eval
workflow, never in `make test-backend`.
"""

from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glean.llm import Feature, LLMModelPolicy, LLMRouter
from glean.receipts import service

from .conftest import _eval_model_id_for
from .receipt_photos import PhotoCase, ScanScore, load_photo_cases, score_scan

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic import SecretStr

    from glean.receipts.schemas import ScanResponse

FEATURE = Feature.RECEIPT_SCAN

OCR_MODES = ["vision", "textract"]
REPORT_PATH = Path(os.environ.get("GLEAN_EVAL_REPORT_DIR", "results")) / "receipt-photo-eval.md"
CASES = load_photo_cases()


@dataclass
class PhotoRun:
    case_id: str
    mode: str
    seconds: float
    response: ScanResponse | None = None
    error: str | None = None
    score: ScanScore | None = None


_RUNS: list[PhotoRun] = []
_MODEL_USED: list[str] = []


def _percent(value: float | None) -> str:
    return "skipped" if value is None else f"{value:.0%}"


def _render_report(model_id: str, runs: list[PhotoRun]) -> str:
    lines = [f"## Receipt photo evals — `{model_id}`", ""]
    for mode in OCR_MODES:
        mode_runs = [r for r in runs if r.mode == mode]
        if not mode_runs:
            lines += [f"### {mode}", "", "Not run (see skip reason in the pytest output).", ""]
            continue
        lines += [
            f"### {mode}",
            "",
            "| Case | Items | Recall | Precision | Quantity | Unit | Price | Category | Non-food dropped | Latency |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in mode_runs:
            if r.score is None or r.response is None:
                lines.append(f"| {r.case_id} | error: {r.error} | | | | | | | | {r.seconds:.1f}s |")
                continue
            s = r.score
            lines.append(
                f"| {r.case_id} | {len(r.response.items)} | {_percent(s.recall)} | {_percent(s.precision)} "
                f"| {_percent(s.quantity_accuracy)} | {_percent(s.unit_accuracy)} | {_percent(s.price_accuracy)} "
                f"| {_percent(s.category_accuracy)} | {_percent(s.non_food_dropped)} | {r.seconds:.1f}s |"
            )
        lines.append("")
    return "\n".join(lines)


@pytest.fixture(scope="module", autouse=True)
def _write_report() -> Iterator[None]:
    yield
    if _RUNS:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report = _render_report(_MODEL_USED[0] if _MODEL_USED else "unknown", _RUNS)
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
    bucket = os.environ.get("GLEAN_EVAL_S3_BUCKET", "")
    if mode == "textract" and not bucket:
        pytest.skip("textract mode needs GLEAN_EVAL_S3_BUCKET (a scratch bucket, never the production one)")
    results = [_scan_case(case, mode, photo_router, bucket) for case in CASES]
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
    seconds = time.perf_counter() - started
    return PhotoRun(case.case_id, mode, seconds, response, score=score_scan(case.expected, response))


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
