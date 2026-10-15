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
from glean.meal_plan.dietary_decisions import DietaryDecision, DietaryDecisionStore
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
