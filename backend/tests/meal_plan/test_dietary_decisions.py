"""Jev dietary decisions in corpus candidate selection (#125).

Seams: `sample_corpus_candidates` (the dietary-filtering step) and the decisions
stored beside the corpus. Decisions are placed through the stored-decision store,
the same blob the producer writes.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

from glean.decisions import JEV_MODEL
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DIETARY_DECISIONS_KEY,
    DIETARY_FLAGS,
    NUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
    DietaryDecision,
    DietaryDecisionStore,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

CURRENT_MODEL = f"{JEV_MODEL}-20260917"


def test_a_recipe_jev_flags_is_excluded_though_the_regex_keeps_it(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"]),
            ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
        ],
    )
    _store_decisions(corpus, {("rec_pesto", "nut-free"): 0.9, ("rec_tomato", "nut-free"): 0.02})

    assert _ids(corpus, ["Nut-Free"]) == {"rec_tomato"}


def test_jev_never_clears_a_recipe_the_regex_excludes(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_satay", "Satay Skewers", ["peanut butter", "tofu"]),
            ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
        ],
    )
    _store_decisions(corpus, {("rec_satay", "nut-free"): 0.0, ("rec_tomato", "nut-free"): 0.0})

    assert _ids(corpus, ["nut-free"]) == {"rec_tomato"}


def test_nut_free_excludes_a_recipe_with_no_stored_decision(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_decided", "Tomato Pasta", ["spaghetti", "tomato"]),
            ("rec_new", "Courgette Pasta", ["spaghetti", "courgette"]),
        ],
    )
    _store_decisions(corpus, {("rec_decided", "nut-free"): 0.01})

    assert _ids(corpus, ["nut-free"]) == {"rec_decided"}


def test_nut_free_excludes_everything_when_no_decisions_are_stored(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])

    assert _ids(corpus, ["nut-free"]) == set()


def test_nut_free_excludes_a_recipe_judged_under_an_older_model(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    _store_decisions(corpus, {("rec_tomato", "nut-free"): 0.01}, model="typesafe/jev-1.12-20260801")

    assert _ids(corpus, ["nut-free"]) == set()


def test_nut_free_excludes_a_recipe_whose_stored_decision_is_unreadable(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    corpus.store.write(DIETARY_DECISIONS_KEY, '{"recipe_id": "rec_tomato", "flag": "nut-fr\n')

    assert _ids(corpus, ["nut-free"]) == set()


def test_preference_flags_without_a_stored_decision_are_judged_by_the_regex_alone(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_chicken", "Chicken Curry", ["chicken thigh", "tomato"]),
            ("rec_dal", "Tomato Dal", ["red lentils", "tomato"]),
        ],
    )

    assert _ids(corpus, ["vegetarian"]) == {"rec_dal"}
    assert _ids(corpus, ["dairy-free", "gluten-free"]) == {"rec_chicken", "rec_dal"}


def test_nut_free_decisions_do_not_leak_into_other_flags(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])])
    _store_decisions(corpus, {("rec_pesto", "nut-free"): 0.9})

    assert _ids(corpus, ["vegetarian"]) == {"rec_pesto"}


def test_nut_free_is_stricter_than_the_preference_flags(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_maybe", "Mystery Stew", ["tomato", "sauce"])])
    # A probability high enough to worry about for an allergy, yet below "probably" for a preference.
    _store_decisions(corpus, {("rec_maybe", flag): 0.3 for flag in DIETARY_FLAGS})

    assert _ids(corpus, ["nut-free"]) == set()
    for flag in ("vegetarian", "vegan", "dairy-free", "gluten-free"):
        assert _ids(corpus, [flag]) == {"rec_maybe"}


def test_a_probability_at_the_threshold_excludes(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_edge", "Edge Stew", ["tomato", "sauce"])])
    _store_decisions(
        corpus, {("rec_edge", "nut-free"): NUT_FREE_THRESHOLD, ("rec_edge", "vegan"): PREFERENCE_THRESHOLD}
    )

    assert _ids(corpus, ["nut-free"]) == set()
    assert _ids(corpus, ["vegan"]) == set()


def _ids(corpus: RecipeCorpusStore, flags: list[str]) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry_names=[],
        dietary_flags=flags,
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=50,
    )
    return {candidate.external_id for candidate in candidates}


def _store_decisions(
    corpus: RecipeCorpusStore, probabilities: dict[tuple[str, str], float], *, model: str = CURRENT_MODEL
) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag=flag,
                probability=probability,
                model=model,
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            for (recipe_id, flag), probability in probabilities.items()
        ]
    )


def _corpus(tmp_path, recipes: list[tuple[str, str, list[str]]]) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title, ingredients in recipes:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    return corpus
