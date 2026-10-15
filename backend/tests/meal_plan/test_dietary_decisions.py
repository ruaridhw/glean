"""dietary decisions in corpus candidate selection (#125).

Seams: `sample_corpus_candidates` (the dietary-filtering step) and the decisions
stored beside the corpus. Decisions are placed through the stored-decision store,
the same blob the producer writes.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

import httpx
import pytest

from glean.decisions import DECISION_MODEL
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DIETARY_DECISIONS_KEY,
    DIETARY_FLAGS,
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

CURRENT_MODEL = f"{DECISION_MODEL}-20261014"


def test_a_recipe_a_stored_decision_flags_is_excluded_though_its_ingredients_look_harmless(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"]),
            ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
        ],
    )
    _store_decisions(corpus, {("rec_pesto", "nut-free"): 0.9, ("rec_tomato", "nut-free"): 0.02})

    assert _ids(corpus, ["Nut-Free"]) == {"rec_tomato"}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_a_stored_decision_alone_decides_so_a_low_probability_keeps_a_recipe_naming_a_forbidden_food(
    tmp_path, flag: str
) -> None:
    corpus = _corpus(tmp_path, [("rec_mixed", "Everything Bowl", ["chicken", "cheese", "peanut", "bread"])])
    _store_decisions(corpus, {("rec_mixed", flag): 0.0})

    assert _ids(corpus, [flag]) == {"rec_mixed"}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_with_no_stored_decision(tmp_path, flag: str) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_decided", "Tomato Pasta", ["spaghetti", "tomato"]),
            ("rec_new", "Courgette Pasta", ["spaghetti", "courgette"]),
        ],
    )
    _store_decisions(corpus, {("rec_decided", flag): 0.01})

    assert _ids(corpus, [flag]) == {"rec_decided"}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_everything_when_no_decisions_are_stored(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])

    assert _ids(corpus, [flag]) == set()


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_judged_under_an_older_model(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    _store_decisions(corpus, {("rec_tomato", flag): 0.01}, model="typesafe/jev-1.13-20260917")

    assert _ids(corpus, [flag]) == set()


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_a_decision_computed_under_other_criteria_text_is_treated_as_missing(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    question = dietary_questions()[flag]
    reworded = question.model_copy(update={"instructions": question.instructions + " Tahini counts."})
    _store_decisions(corpus, {("rec_tomato", flag): 0.01}, criteria_hash=question_hash(reworded))

    assert _ids(corpus, [flag]) == set()


def test_the_criteria_hash_changes_with_either_criterion_or_the_instructions() -> None:
    question = dietary_questions()["vegetarian"]
    criteria = question.criteria

    variants = [
        question.model_copy(update={"instructions": question.instructions + " "}),
        question.model_copy(update={"criteria": criteria.model_copy(update={"true": criteria.true + " "})}),
        question.model_copy(update={"criteria": criteria.model_copy(update={"false": criteria.false + " "})}),
    ]

    assert len({question_hash(question), *(question_hash(variant) for variant in variants)}) == 4


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_whose_stored_decision_is_unreadable(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    corpus.store.write(DIETARY_DECISIONS_KEY, '{"recipe_id": "rec_tomato", "flag": "nut-fr\n')

    assert _ids(corpus, [flag]) == set()


def test_flags_the_decision_model_isnt_asked_about_leave_candidates_alone(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pasta", "Pasta Bake", ["penne", "cheese"])])

    assert _ids(corpus, ["Keto", "Paleo"]) == {"rec_pasta"}


def test_nut_free_decisions_do_not_leak_into_other_flags(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])])
    _store_decisions(corpus, {("rec_pesto", "nut-free"): 0.9, ("rec_pesto", "vegetarian"): 0.0})

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


def test_choosing_candidates_makes_no_network_call(tmp_path, monkeypatch) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    _store_decisions(corpus, {("rec_tomato", flag): 0.0 for flag in DIETARY_FLAGS})

    def refuse(*_args, **_kwargs):
        raise AssertionError("Generate must not call the decision model")

    monkeypatch.setattr(httpx.Client, "send", refuse)

    assert _ids(corpus, ["nut-free", "vegetarian"]) == {"rec_tomato"}


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
    corpus: RecipeCorpusStore,
    probabilities: dict[tuple[str, str], float],
    *,
    model: str = CURRENT_MODEL,
    criteria_hash: str | None = None,
) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag=flag,
                probability=probability,
                model=model,
                content_hash=_hash(corpus, recipe_id),
                criteria_hash=criteria_hash or question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            for (recipe_id, flag), probability in probabilities.items()
        ]
    )


def _hash(corpus: RecipeCorpusStore, recipe_id: str) -> str:
    summary = next(s for s in corpus.search(per_page=1000)[0] if s.external_id == recipe_id)
    return content_fingerprint(summary.title, summary.ingredient_names)


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
