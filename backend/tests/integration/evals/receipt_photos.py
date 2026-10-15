"""Expected-result model and scorer for the receipt photo evals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glean.receipts.schemas import ParsedIngredient, ScanResponse


@dataclass(frozen=True)
class ExpectedItem:
    name: str
    quantity: float
    unit: str
    unit_price: float
    category: str | None = None
    non_food: bool = False

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
class ScanScore:
    recall: float
    precision: float
    quantity_accuracy: float
    unit_accuracy: float
    price_accuracy: float
    category_accuracy: float | None


MATCH_THRESHOLD = 0.6


def _tokens(name: str) -> frozenset[str]:
    """Lowercase word set with a trailing plural 's' dropped, so "limes" and "lime" agree."""
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", name.lower()))


def _similarity(a: str, b: str) -> tuple[float, float]:
    """(share of the shorter name's words found in the other, character ratio as tie-break)."""
    ta, tb = _tokens(a), _tokens(b)
    overlap = len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0
    return overlap, SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _match_one_to_one[W: ExpectedItem](
    wanted: list[W], got: list[ParsedIngredient]
) -> list[tuple[W, ParsedIngredient]]:
    """Best-first assignment so each expected line and each scanned line is used at most once."""
    candidates = sorted(
        (
            (_similarity(w.name, g.name), wi, gi)
            for wi, w in enumerate(wanted)
            for gi, g in enumerate(got)
            if _similarity(w.name, g.name)[0] >= MATCH_THRESHOLD
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


def score_scan(expected: ExpectedReceipt, response: ScanResponse) -> ScanScore:
    food = [item for item in expected.items if not item.non_food]
    pairs = _match_one_to_one(food, response.items)

    def share(hits: int) -> float:
        return hits / len(food) if food else 0.0

    return ScanScore(
        recall=share(len(pairs)),
        precision=len(pairs) / len(response.items) if response.items else 0.0,
        quantity_accuracy=share(sum(1 for w, g in pairs if g.quantity == w.quantity)),
        unit_accuracy=share(sum(1 for w, g in pairs if g.unit == w.unit)),
        price_accuracy=share(sum(1 for w, g in pairs if g.unit_price == w.unit_price)),
        category_accuracy=share(sum(1 for w, g in pairs if g.category == w.category)),
    )
