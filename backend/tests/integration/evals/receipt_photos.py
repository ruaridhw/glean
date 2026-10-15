"""Expected-result model and scorer for the receipt photo evals."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glean.receipts.schemas import ParsedIngredient, ScanResponse


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


def _same_word(a: str, b: str) -> bool:
    """Equal, or inflections of one word ("limes"/"lime", "curled"/"curly"): a shared stem of 3+ letters
    that covers all but at most one letter of the shorter word."""
    prefix = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        prefix += 1
    return a == b or (prefix >= 3 and prefix >= min(len(a), len(b)) - 1)


def _words(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", name.lower())


def _names_match(a: str, b: str) -> bool:
    """Same product: the head noun (last word) agrees, and the modifiers don't contradict each other.

    "egg noodles" is not "eggs" (different head) and "olive oil" is not "sesame oil" (same head,
    disjoint modifiers), while "tesco limes each" ~ "lime" and "curled leaf parsley" ~ "curly parsley".
    """
    wa, wb = _words(a), _words(b)
    if not wa or not wb or not _same_word(wa[-1], wb[-1]):
        return False
    mods_a, mods_b = wa[:-1], wb[:-1]
    if not mods_a or not mods_b:
        return True
    return any(_same_word(x, y) for x in mods_a for y in mods_b)


def _names_of(item: ExpectedItem) -> tuple[str, ...]:
    return (item.name, *item.aliases)


def _match_one_to_one[W: ExpectedItem](
    wanted: list[W], got: list[ParsedIngredient]
) -> list[tuple[W, ParsedIngredient]]:
    """Best-first assignment so each expected line and each scanned line is used at most once."""
    candidates = sorted(
        (
            (max(SequenceMatcher(None, n.lower(), g.name.lower()).ratio() for n in _names_of(w)), wi, gi)
            for wi, w in enumerate(wanted)
            for gi, g in enumerate(got)
            if any(_names_match(n, g.name) for n in _names_of(w))
        ),
        reverse=True,
    )
    used_w: set[int] = set()
    used_g: set[int] = set()
    pairs = []
    for _, wi, gi in candidates:
        if wi in used_w or gi in used_g:
            continue
        used_w.add(wi)
        used_g.add(gi)
        pairs.append((wanted[wi], got[gi]))
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
