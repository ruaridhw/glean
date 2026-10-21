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
    PEANUT_FREE,
    PREFERENCE_THRESHOLD,
    THRESHOLDS,
    TREE_NUT_FREE,
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

# candidate selection treats recipes sharing this fraction of their ingredients as variants of one dish
_NEAR_DUPLICATE_OVERLAP = 0.7

NUT_FLAGS = (TREE_NUT_FREE, PEANUT_FREE)

# Peanut-free is an allergy flag, so its threshold also drops these lookalikes: the model scores dukkah, praline
# (hazelnuts, almonds) and a bare chilli crisp (the shelves list peanut in 1 of 4, so it is not named) 0.45, 0.35 and
# 0.33 for peanuts. Tree-nut-free drops none: pastes score low there. Anything else a
# nut flag drops is a regression.
ACCEPTED_FALSE_EXCLUSIONS = {
    TREE_NUT_FREE: set(),
    PEANUT_FREE: {"table-nut-dukkah", "regex-forbidden-nuts-praline", "allowed-chilli-crisp"},
}

# The margins recorded beside the thresholds in dietary_decisions.py, held to a little under what was measured.
PREFERENCE_MARGIN = 0.10
NUT_MARGIN_ABOVE_CLEAN = {TREE_NUT_FREE: 0.15, PEANUT_FREE: 0.005}
NUT_MARGIN_BELOW_VIOLATORS = {TREE_NUT_FREE: 0.5, PEANUT_FREE: 0.25}


@pytest.fixture(scope="module")
def offered_by_flag(tmp_path_factory) -> dict[str, set[str]]:
    """Ids offered under each flag by corpora of the sample recipes, each decided from its measured probabilities.

    Candidate selection drops near-duplicate recipes, and rows from the two fixtures (and within the sample)
    share ingredient lists (coconut milk, basil pesto), so the rows are split into corpora with no near-duplicates.
    """
    offered = {flag: set() for flag in DIETARY_FLAGS}
    for rows in _without_near_duplicates(ROWS):
        for flag, ids in _offered(tmp_path_factory.mktemp("corpus"), rows).items():
            offered[flag] |= ids
    return offered


def _without_near_duplicates(rows: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for row in rows:
        ingredients = {name.casefold() for name in row["ingredients"]}
        for group in groups:
            if all(
                len(ingredients & other) / len(ingredients | other) < _NEAR_DUPLICATE_OVERLAP
                for other in group_sets(group)
            ):
                group.append(row)
                break
        else:
            groups.append([row])
    return groups


def group_sets(group: list[dict]) -> list[set[str]]:
    return [{name.casefold() for name in row["ingredients"]} for row in group]


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
                pantry=[],
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


@pytest.mark.parametrize("flag", [flag for flag in DIETARY_FLAGS if flag not in NUT_FLAGS])
def test_every_labelled_recipe_that_is_fine_for_a_preference_flag_is_still_offered(offered_by_flag, flag: str) -> None:
    fine = {row["id"] for row in ROWS if row["violates"].get(flag) is False}

    assert fine
    assert fine - offered_by_flag[flag] == set()


@pytest.mark.parametrize("flag", NUT_FLAGS)
def test_each_nut_flag_offers_coconut_milk_nutmeg_butternut_tahini_and_the_ordinary_recipes(
    offered_by_flag, flag: str
) -> None:
    offered = offered_by_flag[flag]

    fine = {row["id"] for row in ROWS if row["violates"].get(flag) is False}
    assert {"allowed-coconut-milk", "allowed-nutmeg", "allowed-butternut", "heldout-nut-tahini"} <= offered
    assert fine - offered == ACCEPTED_FALSE_EXCLUSIONS[flag] & fine


def test_satay_groundnut_oil_and_peanut_butter_pass_tree_nut_free_and_fail_peanut_free(offered_by_flag) -> None:
    peanut_recipes = {
        "regex-forbidden-nuts-satay",
        "heldout-peanut-groundnut-oil",
        "regex-safe-dairy-peanut-butter",
        "ordinary-06",  # chicken satay with peanut butter
    }

    assert peanut_recipes <= offered_by_flag[TREE_NUT_FREE]
    assert peanut_recipes & offered_by_flag[PEANUT_FREE] == set()


def test_pine_nuts_pesto_and_almonds_fail_tree_nut_free_and_pass_peanut_free(offered_by_flag) -> None:
    tree_nut_recipes = {"regex-forbidden-nuts-pine-nut", "table-nut-pesto", "regex-forbidden-nuts-almond"}

    assert tree_nut_recipes & offered_by_flag[TREE_NUT_FREE] == set()
    assert tree_nut_recipes <= offered_by_flag[PEANUT_FREE]


def test_a_korma_tikka_masala_or_pasanda_paste_is_not_excluded_for_either_nut_flag_for_being_that_paste(
    offered_by_flag,
) -> None:
    pastes = {"allowed-korma-paste", "allowed-tikka-masala-seasoning", "allowed-pasanda-paste"}

    assert pastes <= offered_by_flag[TREE_NUT_FREE]
    assert pastes <= offered_by_flag[PEANUT_FREE]


@pytest.mark.parametrize(
    ("row", "flag"),
    [pytest.param(row, flag, id=f"{row['id']}/{flag}") for row in COVERAGE_ROWS for flag in row["violates"]],
)
def test_every_former_regex_term_is_excluded_or_kept_as_the_regex_decided(offered_by_flag, row, flag: str) -> None:
    offered = row["id"] in offered_by_flag[flag]
    accepted_exclusion = row["id"] in ACCEPTED_FALSE_EXCLUSIONS.get(flag, set())

    assert offered == (not row["violates"][flag] and not accepted_exclusion)


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
    threshold = THRESHOLDS.get(flag, PREFERENCE_THRESHOLD)
    violators = [PROBABILITIES[row["id"]][flag] for row in ROWS if row["violates"].get(flag)]
    clean = [
        PROBABILITIES[row["id"]][flag]
        for row in ROWS
        if row["violates"].get(flag) is False and row["id"] not in ACCEPTED_FALSE_EXCLUSIONS.get(flag, set())
    ]

    if flag in NUT_FLAGS:
        assert threshold - max(clean) >= NUT_MARGIN_ABOVE_CLEAN[flag]
        assert min(violators) - threshold >= NUT_MARGIN_BELOW_VIOLATORS[flag]
    else:
        assert threshold - max(clean) >= PREFERENCE_MARGIN
        assert min(violators) - threshold >= PREFERENCE_MARGIN


def test_every_term_of_the_deleted_regex_lists_has_a_labelled_coverage_recipe() -> None:
    """`dietary_regex_terms.json` freezes the lists as they stood in candidates.py before #159 deleted them."""
    inventory = json.loads((FIXTURES / "dietary_regex_terms.json").read_text())
    labelled = {(row["group"], row["kind"], row["term"]): row["violates"] for row in COVERAGE_ROWS}

    expected = {
        (group, kind, term) for group, lists in inventory.items() for kind, terms in lists.items() for term in terms
    }
    assert len(expected) == 169
    assert [context for context in sorted(expected) if not labelled.get(context)] == []


def test_every_coverage_recipe_is_labelled_for_at_least_one_flag() -> None:
    assert [row["id"] for row in COVERAGE_ROWS if not row["violates"]] == []
