from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import backfill_recipe_units

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path


def _seed(cache_dir: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(cache_dir / "corpus"))
    corpus.save(
        StoredRecipe(
            external_id="import:leaky",
            title="Leaky",
            ingredients=[StoredIngredient(canonical_name="Oz cheddar", quantity=8, unit="pcs")],
        )
    )
    return corpus


def test_script_defaults_to_a_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus = _seed(tmp_path)

    assert backfill_recipe_units.main(["--cache-dir", str(tmp_path)]) == 0

    assert corpus.get("import:leaky").ingredients[0].canonical_name == "Oz cheddar"
    assert "1 ingredients in 1 recipes" in capsys.readouterr().out


def test_script_writes_the_local_corpus_with_write_flag(tmp_path: Path) -> None:
    corpus = _seed(tmp_path)

    assert backfill_recipe_units.main(["--cache-dir", str(tmp_path), "--write"]) == 0

    ingredient = corpus.get("import:leaky").ingredients[0]
    assert (ingredient.canonical_name, ingredient.unit) == ("Cheddar", "g")


def test_script_has_no_way_to_target_s3() -> None:
    with pytest.raises(SystemExit):
        backfill_recipe_units.main(["--bucket", "some-prod-bucket"])
