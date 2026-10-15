from __future__ import annotations

from glean.receipts.schemas import ParsedIngredient, ScanResponse
from tests.integration.evals.receipt_photos import ExpectedItem, ExpectedReceipt, score_scan


def _expected(*items: ExpectedItem) -> ExpectedReceipt:
    return ExpectedReceipt(items=list(items), subtotal=0.0, savings=0.0, total=0.0)


def _scan(*items: ParsedIngredient) -> ScanResponse:
    return ScanResponse(items=list(items))


def _parsed(name: str, quantity: float, unit: str, unit_price: float, category: str | None = None) -> ParsedIngredient:
    return ParsedIngredient(
        name=name, quantity=quantity, unit=unit, unit_price=unit_price, confidence=0.9, category=category
    )


MILK = ExpectedItem(name="semi skimmed milk", quantity=1136, unit="ml", unit_price=1.20 / 1136, category="dairy")


class TestScoreScan:
    def test_a_scan_identical_to_the_expected_receipt_scores_perfectly(self) -> None:
        score = score_scan(_expected(MILK), _scan(_parsed("semi skimmed milk", 1136, "ml", 1.20 / 1136, "dairy")))

        assert (score.recall, score.precision) == (1.0, 1.0)
        assert (score.quantity_accuracy, score.unit_accuracy, score.price_accuracy) == (1.0, 1.0, 1.0)
        assert score.category_accuracy == 1.0

    def test_an_empty_scan_scores_zero_without_error(self) -> None:
        score = score_scan(_expected(MILK), _scan())

        assert (score.recall, score.precision, score.price_accuracy) == (0.0, 0.0, 0.0)

    def test_names_match_despite_store_brand_prefix_and_plural(self) -> None:
        limes = ExpectedItem(name="limes", quantity=1, unit="units", unit_price=0.23)

        score = score_scan(_expected(limes), _scan(_parsed("tesco lime", 1, "units", 0.23)))

        assert score.recall == 1.0

    def test_one_scanned_line_cannot_satisfy_two_expected_lines(self) -> None:
        chopped = ExpectedItem(name="chopped tomatoes", quantity=400, unit="g", unit_price=1.05 / 400)
        baby_plum = ExpectedItem(name="baby plum tomatoes", quantity=250, unit="g", unit_price=1.35 / 250)

        score = score_scan(_expected(chopped, baby_plum), _scan(_parsed("chopped tomatoes", 400, "g", 1.05 / 400)))

        assert (score.recall, score.precision) == (0.5, 1.0)
