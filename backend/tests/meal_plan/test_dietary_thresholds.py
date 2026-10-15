"""The labelled sample replayed through real candidate selection (#125).

`tests/fixtures/decisions/dietary_sample.json` labels which flags each recipe violates: every
row of the issue's table, the allowed cases (coconut milk, nutmeg, parmesan under
vegetarian, gluten-free oats), held-out items the criteria don't name, and ordinary
recipes. `dietary_sample_measured.json` holds the probabilities the live model gave on
2026-10-15 (re-check with `tests/integration/test_dietary_sample_live.py`). Here those
answers are stored as decisions beside a corpus of the sample's recipes, and
`sample_corpus_candidates` decides what each flag offers.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest

from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DIETARY_FLAGS,
    NUT_FREE,
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
ROWS = json.loads((FIXTURES / "dietary_sample.json").read_text())["rows"]
_MEASURED = json.loads((FIXTURES / "dietary_sample_measured.json").read_text())
PROBABILITIES = _MEASURED["probabilities"]
MODEL = _MEASURED["model"]

# Nut-free is an allergy, so its strict threshold also drops these nut-butter lookalikes
# (tahini 0.20, hummus wrap 0.15). Anything else it drops is a regression.
ACCEPTED_NUT_FREE_FALSE_EXCLUSIONS = {"heldout-nut-tahini", "ordinary-15"}


def _replay(tmp_path: Path, flag: str) -> tuple[set[str], set[str]]:
    """Returns (ids offered under `flag`, ids of the sample rows labelled for `flag`)."""
    labelled = [row for row in ROWS if flag in row["violates"]]
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for row in labelled:
        corpus.save(
            StoredRecipe(
                external_id=row["id"],
                title=row["title"],
                ingredients=[
                    StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in row["ingredients"]
                ],
            )
        )
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=row["id"],
                flag=decided_flag,
                probability=PROBABILITIES[row["id"]][decided_flag],
                model=MODEL,
                content_hash=content_fingerprint(row["title"], row["ingredients"]),
                criteria_hash=question_hash(dietary_questions()[decided_flag]),
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            for row in labelled
            for decided_flag in DIETARY_FLAGS
        ]
    )
    offered = sample_corpus_candidates(
        corpus,
        pantry_names=[],
        dietary_flags=[flag],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=1000,
    )
    return {candidate.external_id for candidate in offered}, {row["id"] for row in labelled}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_labelled_recipe_that_breaks_the_flag_is_left_out(tmp_path, flag: str) -> None:
    offered, labelled = _replay(tmp_path, flag)

    violators = {row["id"] for row in ROWS if row["violates"].get(flag)}
    assert violators <= labelled
    assert offered & violators == set()


@pytest.mark.parametrize("flag", [flag for flag in DIETARY_FLAGS if flag != NUT_FREE])
def test_every_labelled_recipe_that_is_fine_for_a_preference_flag_is_still_offered(tmp_path, flag: str) -> None:
    offered, labelled = _replay(tmp_path, flag)

    fine = {row["id"] for row in ROWS if row["violates"].get(flag) is False}
    assert fine <= labelled
    assert fine - offered == set()


def test_nut_free_still_offers_coconut_milk_nutmeg_butternut_and_the_ordinary_recipes(tmp_path) -> None:
    offered, _ = _replay(tmp_path, NUT_FREE)

    fine = {row["id"] for row in ROWS if row["violates"].get(NUT_FREE) is False}
    assert {"allowed-coconut-milk", "allowed-nutmeg", "allowed-butternut"} <= offered
    assert fine - offered == ACCEPTED_NUT_FREE_FALSE_EXCLUSIONS & fine
