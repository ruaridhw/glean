from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from glean.receipts.schemas import ParsedIngredient, ScanResponse
from tests.integration.evals.receipt_photos import (
    UNIT_VOCABULARY,
    ExpectedItem,
    ExpectedReceipt,
    load_photo_cases,
    score_scan,
)

if TYPE_CHECKING:
    from pathlib import Path


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

    def test_names_match_across_inflection_of_a_modifier(self) -> None:
        parsley = ExpectedItem(name="curly parsley", quantity=30, unit="g", unit_price=0.5 / 30)

        score = score_scan(_expected(parsley), _scan(_parsed("curled leaf parsley", 30, "g", 0.5 / 30)))

        assert (score.recall, score.precision) == (1.0, 1.0)

    def test_a_modifier_cannot_stand_in_for_a_different_head_noun(self) -> None:
        eggs = ExpectedItem(name="eggs", quantity=6, unit="units", unit_price=2.5 / 6)

        score = score_scan(_expected(eggs), _scan(_parsed("egg noodles", 6, "units", 2.5 / 6)))

        assert (score.recall, score.precision) == (0.0, 0.0)

    @pytest.mark.parametrize(
        ("expected_name", "scanned_name"),
        [
            ("olive oil", "sesame oil"),
            ("sesame seeds", "sesame oil"),
            ("chopped tomatoes", "baby plum tomatoes"),
            ("lemons", "lemon juice"),
        ],
    )
    def test_different_products_sharing_a_word_do_not_match(self, expected_name: str, scanned_name: str) -> None:
        item = ExpectedItem(name=expected_name, quantity=1, unit="units", unit_price=1.0)

        assert score_scan(_expected(item), _scan(_parsed(scanned_name, 1, "units", 1.0))).recall == 0.0

    def test_a_reviewed_alias_matches_when_the_head_noun_differs(self) -> None:
        paneer = ExpectedItem(name="paneer cheese", quantity=200, unit="g", unit_price=0.009, aliases=("paneer",))

        assert score_scan(_expected(paneer), _scan(_parsed("paneer", 200, "g", 0.009))).recall == 1.0

    def test_price_is_judged_on_the_line_total_so_unit_normalisation_does_not_matter(self) -> None:
        herbs = ExpectedItem(name="curled leaf parsley", quantity=30, unit="g", unit_price=0.50 / 30)
        as_one_unit = _parsed("curled leaf parsley", 1, "units", 0.51)
        as_wrong_price = _parsed("curled leaf parsley", 30, "g", 0.60 / 30)

        assert score_scan(_expected(herbs), _scan(as_one_unit)).price_accuracy == 1.0  # £0.51 is within 2p of £0.50
        assert score_scan(_expected(herbs), _scan(as_wrong_price)).price_accuracy == 0.0

    def test_quantity_tolerates_one_percent_and_flags_real_differences(self) -> None:
        oil = ExpectedItem(name="olive oil", quantity=500, unit="ml", unit_price=5.0 / 500)

        close = score_scan(_expected(oil), _scan(_parsed("olive oil", 502, "ml", 5.0 / 502)))
        far = score_scan(_expected(oil), _scan(_parsed("olive oil", 1, "bottle", 5.0)))

        assert (close.quantity_accuracy, far.quantity_accuracy) == (1.0, 0.0)

    def test_a_correct_pack_is_not_a_unit_error(self) -> None:
        potatoes = ExpectedItem(name="jacket potatoes", quantity=1, unit="pack", unit_price=1.70)

        score = score_scan(_expected(potatoes), _scan(_parsed("jacket potatoes", 1, "pack", 1.70)))

        assert score.unit_accuracy == 1.0

    @pytest.mark.parametrize("unit", ["g", "ml", "units", "pack", "bottle"])
    def test_every_unit_in_the_response_vocabulary_is_accepted_in_expected_results(self, unit: str) -> None:
        assert ExpectedItem(name="x", quantity=1, unit=unit, unit_price=1.0).unit == unit

    def test_an_expected_unit_outside_the_response_vocabulary_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="kg"):
            ExpectedItem(name="x", quantity=1, unit="kg", unit_price=1.0)

    def test_category_is_skipped_not_zero_when_the_scan_returned_no_categories(self) -> None:
        score = score_scan(_expected(MILK), _scan(_parsed("semi skimmed milk", 1136, "ml", 1.20 / 1136, None)))

        assert score.category_accuracy is None

    def test_category_is_scored_on_matched_items_that_have_an_expected_category(self) -> None:
        eggs = ExpectedItem(name="free range eggs", quantity=6, unit="units", unit_price=2.50 / 6, category="eggs")
        scan = _scan(
            _parsed("semi skimmed milk", 1136, "ml", 1.20 / 1136, "dairy"),
            _parsed("free range eggs", 6, "units", 2.50 / 6, "dairy"),
        )

        assert score_scan(_expected(MILK, eggs), scan).category_accuracy == 0.5

    def test_unit_vocabulary_matches_what_the_response_schema_documents(self) -> None:
        documented = ParsedIngredient.model_fields["unit"].description or ""

        assert set(re.findall(r'"(\w+)"', documented)) == UNIT_VOCABULARY

    def test_non_food_lines_the_scan_dropped_score_as_dropped(self) -> None:
        shampoo = ExpectedItem(name="shampoo", quantity=1, unit="bottle", unit_price=6.0, non_food=True)
        lint = ExpectedItem(name="lint roller", quantity=1, unit="units", unit_price=2.5, non_food=True)

        dropped_one = _scan(_parsed("semi skimmed milk", 1136, "ml", 1.20 / 1136), _parsed("shampoo", 1, "bottle", 6.0))
        score = score_scan(_expected(MILK, shampoo, lint), dropped_one)

        assert score.non_food_dropped == 0.5

    def test_kept_non_food_lowers_precision_but_not_recall(self) -> None:
        shampoo = ExpectedItem(name="shampoo", quantity=1, unit="bottle", unit_price=6.0, non_food=True)
        scan = _scan(_parsed("semi skimmed milk", 1136, "ml", 1.20 / 1136), _parsed("shampoo", 1, "bottle", 6.0))

        score = score_scan(_expected(MILK, shampoo), scan)

        assert (score.recall, score.precision) == (1.0, 0.5)

    def test_non_food_is_not_applicable_on_a_receipt_with_none(self) -> None:
        assert score_scan(_expected(MILK), _scan()).non_food_dropped is None


class TestLoadPhotoCases:
    def test_photos_of_one_receipt_share_its_expected_result(self, tmp_path: Path) -> None:
        receipt = tmp_path / "long-shop"
        receipt.mkdir()
        (receipt / "glare.jpg").write_bytes(b"jpeg")
        (receipt / "shadow.jpg").write_bytes(b"jpeg")
        (receipt / "expected.json").write_text(
            json.dumps(
                {
                    "subtotal": 5.0,
                    "savings": 1.0,
                    "total": 4.0,
                    "items": [
                        {"name": "milk", "quantity": 1136, "unit": "ml", "unit_price": 0.001, "category": "dairy"},
                        {"name": "shampoo", "quantity": 1, "unit": "bottle", "unit_price": 3.0, "non_food": True},
                    ],
                }
            )
        )

        cases = load_photo_cases(tmp_path)

        assert [c.case_id for c in cases] == ["long-shop/glare", "long-shop/shadow"]
        assert cases[0].expected is cases[1].expected
        assert [(i.name, i.non_food, i.category) for i in cases[0].expected.items] == [
            ("milk", False, "dairy"),
            ("shampoo", True, None),
        ]
        assert cases[0].image_path == receipt / "glare.jpg"
