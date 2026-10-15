from __future__ import annotations

from pathlib import Path

from PIL import Image

from tests.integration.evals.receipt_photos import load_photo_cases

FIXTURES = Path(__file__).parent / "integration" / "evals" / "fixtures"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _fixture_images() -> list[Path]:
    return sorted(p for p in FIXTURES.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


class TestFixtureImagePrivacy:
    def test_there_are_fixture_images_to_check(self) -> None:
        assert len(_fixture_images()) == 5

    def test_every_committed_fixture_image_has_no_exif(self) -> None:
        leaking = []
        for path in _fixture_images():
            with Image.open(path) as image:
                if image.getexif() or {"exif", "xmp", "icc_profile"} & set(image.info):
                    leaking.append(str(path.relative_to(FIXTURES)))
        assert not leaking, f"fixture images carry metadata: {leaking}"


class TestExpectedResults:
    def test_five_photos_of_four_receipts_with_glare_and_shadow_sharing_one_result(self) -> None:
        cases = load_photo_cases()

        assert len(cases) == 5
        assert len({id(c.expected) for c in cases}) == 4
        glare, shadow = (c for c in cases if c.case_id.startswith("long-food-shop/"))
        assert glare.expected is shadow.expected

    def test_item_prices_net_of_discounts_reconcile_with_the_printed_total(self) -> None:
        for case in load_photo_cases():
            receipt = case.expected
            net = round(sum(item.line_total for item in receipt.items), 2)
            assert net == receipt.total, f"{case.case_id}: items sum to {net}, printed total {receipt.total}"
            assert round(receipt.subtotal - receipt.savings, 2) == receipt.total, case.case_id

    def test_the_receipts_exercise_non_food_flagging(self) -> None:
        flagged = {c.case_id.split("/")[0]: sum(i.non_food for i in c.expected.items) for c in load_photo_cases()}

        assert flagged["long-food-shop"] == 0
        assert flagged["non-food-multibuy"] >= 3
        assert flagged["mixed-food-cleaning"] >= 1
        assert flagged["meal-deal"] >= 1
