"""The labelled samples replayed through real candidate selection (#125, #159).

Two fixtures in `tests/fixtures/decisions/` label which flags each recipe violates:
`dietary_sample.json` holds every row of #125's table, the allowed cases (coconut milk, nutmeg,
parmesan under vegetarian, gluten-free oats), held-out items the criteria don't name and ordinary recipes;
`dietary_regex_coverage.json` holds one recipe per forbidden word and per safe qualifier of the dietary
regex rules #159 deleted (each labelled by what that regex decided, "potato gnocchi" excepted). The
`*_measured.json` files hold the probabilities the live model gave on 2026-10-15 (re-check with
`tests/integration/test_dietary_sample_live.py`). Here those answers are stored as decisions beside a
corpus of the recipes, and `sample_corpus_candidates` decides what each flag offers.
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
    NUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
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
_FILES = ("dietary_sample", "dietary_regex_coverage")
SAMPLE_ROWS = json.loads((FIXTURES / "dietary_sample.json").read_text())["rows"]
COVERAGE_ROWS = json.loads((FIXTURES / "dietary_regex_coverage.json").read_text())["rows"]
ROWS = SAMPLE_ROWS + COVERAGE_ROWS
_MEASURED = [json.loads((FIXTURES / f"{name}_measured.json").read_text()) for name in _FILES]
PROBABILITIES = {row_id: answers for measured in _MEASURED for row_id, answers in measured["probabilities"].items()}
MODELS = {measured["model"] for measured in _MEASURED}

# Nut-free is an allergy, so its strict threshold also drops these nut-butter lookalikes
# (tahini 0.18, hummus wrap 0.15). Anything else it drops is a regression.
ACCEPTED_NUT_FREE_FALSE_EXCLUSIONS = {"heldout-nut-tahini", "ordinary-15"}

# The margins recorded beside the thresholds in dietary_decisions.py, held to a little under what was measured.
PREFERENCE_MARGIN = 0.15
NUT_FREE_MARGIN_ABOVE_CLEAN = 0.02
NUT_FREE_MARGIN_BELOW_VIOLATORS = 0.5


@pytest.fixture(scope="module")
def offered_by_flag(tmp_path_factory) -> dict[str, set[str]]:
    """Ids offered under each flag by corpora of the sample recipes, each decided from its measured probabilities.

    Each fixture gets its own corpus: candidate selection drops near-duplicate recipes, and the two fixtures
    share ingredients (coconut milk) that would otherwise knock each other out.
    """
    offered = {flag: set() for flag in DIETARY_FLAGS}
    for rows in (SAMPLE_ROWS, COVERAGE_ROWS):
        for flag, ids in _offered(tmp_path_factory.mktemp("corpus"), rows).items():
            offered[flag] |= ids
    return offered


def _offered(root: Path, rows: list[dict]) -> dict[str, set[str]]:
    (model,) = MODELS
    corpus = RecipeCorpusStore(FilesystemBlobStore(root))
    for row in rows:
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
                flag=flag,
                probability=PROBABILITIES[row["id"]][flag],
                model=model,
                content_hash=content_fingerprint(row["title"], row["ingredients"]),
                criteria_hash=question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            for row in rows
            for flag in DIETARY_FLAGS
        ]
    )
    return {
        flag: {
            candidate.external_id
            for candidate in sample_corpus_candidates(
                corpus,
                pantry_names=[],
                dietary_flags=[flag],
                max_total_time_mins=None,
                exclude_external_ids=[],
                rng=random.Random(0),
                sample_size=1000,
            )
        }
        for flag in DIETARY_FLAGS
    }


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_labelled_recipe_that_breaks_the_flag_is_left_out(offered_by_flag, flag: str) -> None:
    violators = {row["id"] for row in ROWS if row["violates"].get(flag)}

    assert violators
    assert offered_by_flag[flag] & violators == set()


@pytest.mark.parametrize("flag", [flag for flag in DIETARY_FLAGS if flag != NUT_FREE])
def test_every_labelled_recipe_that_is_fine_for_a_preference_flag_is_still_offered(offered_by_flag, flag: str) -> None:
    fine = {row["id"] for row in ROWS if row["violates"].get(flag) is False}

    assert fine
    assert fine - offered_by_flag[flag] == set()


def test_nut_free_still_offers_coconut_milk_nutmeg_butternut_and_the_ordinary_recipes(offered_by_flag) -> None:
    offered = offered_by_flag[NUT_FREE]

    fine = {row["id"] for row in ROWS if row["violates"].get(NUT_FREE) is False}
    assert {"allowed-coconut-milk", "allowed-nutmeg", "allowed-butternut"} <= offered
    assert fine - offered == ACCEPTED_NUT_FREE_FALSE_EXCLUSIONS & fine


@pytest.mark.parametrize(
    ("row", "flag"),
    [pytest.param(row, flag, id=f"{row['id']}/{flag}") for row in COVERAGE_ROWS for flag in row["violates"]],
)
def test_every_former_regex_term_is_excluded_or_kept_as_the_regex_decided(offered_by_flag, row, flag: str) -> None:
    offered = row["id"] in offered_by_flag[flag]

    assert offered == (not row["violates"][flag])


def test_the_regex_coverage_labels_every_forbidden_word_and_safe_qualifier() -> None:
    forbidden = {row["term"] for row in COVERAGE_ROWS if row["kind"] == "forbidden"}
    safe = {row["term"] for row in COVERAGE_ROWS if row["kind"] == "safe"}

    assert {
        "chicken",
        "worcestershire",
        "sea bass",
        "mayo",
        "ketjap manis",
        "soy sauce",
        "pine nut",
        "praline",
    } <= forbidden
    assert {"vegan", "meat-free", "coconut", "oat", "gluten-free", "rice", "potato", "nut-free", "nutmeg"} <= safe
    assert len(forbidden) == 126


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_the_thresholds_keep_their_recorded_margins_on_the_measured_sample(flag: str) -> None:
    threshold = NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD
    violators = [PROBABILITIES[row["id"]][flag] for row in ROWS if row["violates"].get(flag)]
    clean = [
        PROBABILITIES[row["id"]][flag]
        for row in ROWS
        if row["violates"].get(flag) is False and row["id"] not in ACCEPTED_NUT_FREE_FALSE_EXCLUSIONS
    ]

    if flag == NUT_FREE:
        assert threshold - max(clean) >= NUT_FREE_MARGIN_ABOVE_CLEAN
        assert min(violators) - threshold >= NUT_FREE_MARGIN_BELOW_VIOLATORS
    else:
        assert threshold - max(clean) >= PREFERENCE_MARGIN
        assert min(violators) - threshold >= PREFERENCE_MARGIN
