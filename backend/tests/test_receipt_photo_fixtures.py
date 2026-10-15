from __future__ import annotations

from pathlib import Path

from PIL import Image

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
