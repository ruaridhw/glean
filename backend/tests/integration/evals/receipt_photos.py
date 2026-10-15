"""Expected-result model and scorer for the receipt photo evals."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from glean.receipts.schemas import ParsedIngredient, ScanResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# The unit vocabulary the scan response schema documents (ParsedIngredient.unit in receipts/schemas.py).
UNIT_VOCABULARY = frozenset({"g", "ml", "units", "pack", "bottle"})


@dataclass(frozen=True)
class ExpectedItem:
    name: str
    quantity: float
    unit: str
    unit_price: float
    category: str | None = None
    non_food: bool = False
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.unit not in UNIT_VOCABULARY:
            raise ValueError(f"{self.name!r}: unit {self.unit!r} is not one of {sorted(UNIT_VOCABULARY)}")

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price


@dataclass(frozen=True)
class ExpectedReceipt:
    items: list[ExpectedItem]
    subtotal: float
    savings: float
    total: float


@dataclass(frozen=True)
class PhotoCase:
    case_id: str
    image_path: Path
    expected: ExpectedReceipt


PHOTO_FIXTURES = Path(__file__).parent / "fixtures" / "receipt_photos"


def load_photo_cases(root: Path = PHOTO_FIXTURES) -> list[PhotoCase]:
    """One case per photo; photos in the same receipt directory share its expected.json."""
    cases = []
    for expected_path in sorted(root.glob("*/expected.json")):
        raw = json.loads(expected_path.read_text())
        expected = ExpectedReceipt(
            items=[
                ExpectedItem(
                    name=item["name"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    unit_price=item["unit_price"],
                    category=item.get("category"),
                    non_food=item.get("non_food", False),
                    aliases=tuple(item.get("aliases", ())),
                )
                for item in raw["items"]
            ],
            subtotal=raw["subtotal"],
            savings=raw["savings"],
            total=raw["total"],
        )
        receipt_dir = expected_path.parent
        cases.extend(
            PhotoCase(f"{receipt_dir.name}/{image.stem}", image, expected)
            for image in sorted(receipt_dir.glob("*.jpg"))
        )
    return cases


@dataclass(frozen=True)
class ScanScore:
    recall: float
    precision: float
    quantity_accuracy: float
    unit_accuracy: float
    price_accuracy: float
    category_accuracy: float | None
    non_food_dropped: float | None


PRICE_TOLERANCE_GBP = 0.02
QUANTITY_TOLERANCE = 0.01


# Packaging and marketing words that never change which product a line is. Only these may differ
# between a scanned name and an expected name; anything else needs a reviewed alias.
NOISE_WORDS = frozenset(
    {"tesco", "finest", "british", "large", "ready", "to", "eat", "each", "loose", "pack", "fillet", "fresh", "cut"}
)


def _singular(word: str) -> str:
    """Tiny explicit plural rules: leaves -> leaf, berries -> berry, boxes/tomatoes -> box/tomato, limes -> lime."""
    if len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word == "leaves":
        return "leaf"
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("sses", "xes", "zes", "ches", "shes", "oes")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def normalised_name(name: str) -> frozenset[str]:
    """Lowercase words, punctuation dropped, singularised, packaging words removed."""
    words = [_singular(w) for w in re.findall(r"[a-z0-9]+", name.lower().replace("'", ""))]
    core = frozenset(w for w in words if w not in NOISE_WORDS)
    return core or frozenset(words)


def _names_match(a: str, b: str) -> bool:
    return normalised_name(a) == normalised_name(b)


def _names_of(item: ExpectedItem) -> tuple[str, ...]:
    return (item.name, *item.aliases)


def _match_one_to_one[W: ExpectedItem](
    wanted: list[W], got: list[ParsedIngredient]
) -> list[tuple[W, ParsedIngredient]]:
    """Each expected line takes the first unused scanned line with a matching name."""
    used: set[int] = set()
    pairs = []
    for want in wanted:
        for gi, g in enumerate(got):
            if gi not in used and any(_names_match(n, g.name) for n in _names_of(want)):
                used.add(gi)
                pairs.append((want, g))
                break
    return pairs


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _line_total_close(want: ExpectedItem, got: ParsedIngredient) -> bool:
    return got.unit_price is not None and _close(got.quantity * got.unit_price, want.line_total, PRICE_TOLERANCE_GBP)


def _category_accuracy(
    food: list[ExpectedItem], pairs: list[tuple[ExpectedItem, ParsedIngredient]], response: ScanResponse
) -> float | None:
    """None (skipped) when the backend returned no categories at all: absence is not a zero score."""
    categorised = [item for item in food if item.category is not None]
    if not categorised or all(item.category is None for item in response.items):
        return None
    return sum(1 for want, got in pairs if want.category is not None and got.category == want.category) / len(
        categorised
    )


def score_scan(expected: ExpectedReceipt, response: ScanResponse) -> ScanScore:
    food = [item for item in expected.items if not item.non_food]
    non_food = [item for item in expected.items if item.non_food]
    pairs = _match_one_to_one(food, response.items)
    matched_scan_lines = {id(got) for _, got in pairs}
    leftover = [g for g in response.items if id(g) not in matched_scan_lines]
    kept_non_food = len(_match_one_to_one(non_food, leftover))

    def share(hits: int) -> float:
        return hits / len(food) if food else 0.0

    return ScanScore(
        recall=share(len(pairs)),
        precision=len(pairs) / len(response.items) if response.items else 0.0,
        quantity_accuracy=share(
            sum(1 for w, g in pairs if _close(g.quantity, w.quantity, QUANTITY_TOLERANCE * w.quantity))
        ),
        unit_accuracy=share(sum(1 for w, g in pairs if g.unit == w.unit)),
        price_accuracy=share(sum(1 for w, g in pairs if _line_total_close(w, g))),
        category_accuracy=_category_accuracy(food, pairs, response),
        non_food_dropped=1 - kept_non_food / len(non_food) if non_food else None,
    )


@dataclass
class PhotoRun:
    case_id: str
    mode: str
    seconds: float
    response: ScanResponse | None = None
    error: str | None = None
    score: ScanScore | None = None


def scan_once(
    cache_dir: Path | None, mode: str, model_id: str, scan: Callable[[], list[PhotoRun]]
) -> tuple[list[PhotoRun], bool]:
    """Run the paid scans for one OCR mode once per dispatch, however many pytest processes ask.

    Returns the runs and whether they were freshly scanned (False: read back from the cache).
    """
    cache_file = cache_dir / f"receipt-photo-scans-{mode}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        cached = json.loads(cache_file.read_text())
        if cached["model"] == model_id:
            return [_run_from_json(mode, raw) for raw in cached["runs"]], False
    runs = scan()
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"model": model_id, "runs": [_run_to_json(r) for r in runs]}))
    return runs, True


def _run_to_json(run: PhotoRun) -> dict[str, object]:
    response = run.response.model_dump(exclude={"items": {"__all__": {"food_group"}}}) if run.response else None
    return {"case_id": run.case_id, "seconds": run.seconds, "response": response, "error": run.error}


def _run_from_json(mode: str, raw: dict[str, object]) -> PhotoRun:
    response = ScanResponse.model_validate(raw["response"]) if raw["response"] else None
    return PhotoRun(str(raw["case_id"]), mode, float(raw["seconds"]), response, raw["error"])  # ty: ignore[invalid-argument-type]


_BUCKET_VAR = "GLEAN_EVAL_S3_BUCKET"
_ROLE_VAR = "GLEAN_EVAL_AWS_ROLE_ARN"


def textract_configuration(environ: Mapping[str, str]) -> str | None:
    """The scratch bucket when Textract evals are configured, None when not at all, an error when half."""
    bucket, role = environ.get(_BUCKET_VAR, ""), environ.get(_ROLE_VAR, "")
    if bucket and role:
        return bucket
    if bucket or role:
        missing = _ROLE_VAR if bucket else _BUCKET_VAR
        raise ValueError(f"Textract evals are half configured: {missing} is not set")
    return None


OCR_MODES = ["vision", "textract"]


def _percent(value: float | None) -> str:
    return "skipped" if value is None else f"{value:.0%}"


def render_report(model_id: str, runs: list[PhotoRun], *, textract_configured: bool) -> str:
    lines = [f"## Receipt photo evals — `{model_id}`", ""]
    if not textract_configured:
        lines += [
            f"**textract: not configured** — this run covered `vision` only. Set the repo variables `{_BUCKET_VAR}` "
            f"(a scratch bucket, never the production one) and `{_ROLE_VAR}` to evaluate the Textract path.",
            "",
        ]
    for mode in OCR_MODES:
        mode_runs = [r for r in runs if r.mode == mode]
        if not mode_runs:
            lines += [f"### {mode}", "", "Not run.", ""]
            continue
        lines += [
            f"### {mode}",
            "",
            "| Case | Items | Recall | Precision | Quantity | Unit | Price | Category | Non-food dropped | Latency |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in mode_runs:
            if r.response is None:
                lines.append(f"| {r.case_id} | error: {r.error} | | | | | | | | {r.seconds:.1f}s |")
            elif r.score is None:
                lines.append(f"| {r.case_id} | {len(r.response.items)} | | | | | | | | {r.seconds:.1f}s |")
            else:
                s = r.score
                lines.append(
                    f"| {r.case_id} | {len(r.response.items)} | {_percent(s.recall)} | {_percent(s.precision)} "
                    f"| {_percent(s.quantity_accuracy)} | {_percent(s.unit_accuracy)} | {_percent(s.price_accuracy)} "
                    f"| {_percent(s.category_accuracy)} | {_percent(s.non_food_dropped)} | {r.seconds:.1f}s |"
                )
        lines.append("")
    return "\n".join(lines)
