"""The household profile in the offer (V13b, spec 6.2 step 5): favourites and a few liked recipes reach the model.

Seam: `pipeline.prepare` over a synthetic corpus with stored attribute answers, read through what it offered. The
corpus is far bigger than the 25-recipe offer and nothing matches the pantry, so without the profile a favourite or
a liked cuisine reaches the offer only by chance. Misses the scorer's own terms (`test_profile_planning.py`).
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from glean.meal_plan import pipeline
from glean.meal_plan.candidates import SAMPLE_SIZE
from glean.meal_plan.schemas import MealPlanRequest
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.enrichment.attributes import attribute_questions
from glean.recipes.stored import StoredIngredient, StoredRecipe
from tests.recipes.enrichment.fakes import SNAPSHOT

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)
RECIPES = 200
# Every tenth recipe is Japanese fish; the rest are British chicken.
JAPANESE_FISH = {f"rec_{n:03d}" for n in range(0, RECIPES, 10)}


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for n in range(RECIPES):
        corpus.save(
            StoredRecipe(
                external_id=f"rec_{n:03d}",
                title=f"Dinner {n:03d}",
                total_time_mins=30,
                ingredients=[StoredIngredient(canonical_name=f"thing{n}", quantity=1, unit="each")],
            )
        )
    questions = dict(attribute_questions())
    summaries = {s.external_id: s for s in corpus.search(per_page=10_000)[0]}
    answers = []
    for recipe_id, summary in summaries.items():
        special = recipe_id in JAPANESE_FISH
        for attribute, value in (
            ("cuisine", "japanese" if special else "british"),
            ("main_protein", "fish" if special else "chicken"),
        ):
            question = questions[attribute]
            answers.append(
                RecipeAnswer(
                    recipe_id=recipe_id,
                    question=question.name,
                    probability=0.95,
                    value=value,
                    model=SNAPSHOT,
                    content_hash=content_fingerprint(summary.title, summary.ingredient_names),
                    criteria_hash=question.criteria_hash,
                    computed_at=NOW,
                )
            )
    corpus.save_answers(answers)
    return corpus


def _offered(corpus: RecipeCorpusStore, profile: dict[str, Any] | None, seed: int = 1) -> list[str]:
    request = MealPlanRequest.model_validate(
        {
            "source": "corpus",
            "pantry": [],
            "purchase_tolerance": 1.0,
            "meals_per_week": 5,
            "dietary_flags": [],
            "max_active_time_mins": None,
            "profile": profile,
        }
    )
    return pipeline.prepare(request, corpus=corpus, rng=random.Random(seed), now=NOW).offered_ids


def test_without_a_profile_the_offer_is_unchanged_by_this_slice(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)

    # An empty profile asks for nothing, so it draws exactly the offer no profile does.
    assert _offered(corpus, None) == _offered(corpus, {})
    assert len(_offered(corpus, None)) == SAMPLE_SIZE


def test_every_eligible_favourite_is_offered(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    plain = _offered(corpus, None)
    missing = [f"rec_{n:03d}" for n in range(1, RECIPES) if f"rec_{n:03d}" not in plain][:2]

    offered = _offered(
        corpus,
        {
            "favourite_meals": [
                {"text": "Not the title", "recipe_id": missing[0]},
                {"text": f"dinner {missing[1][-3:]}"},
            ]
        },
    )

    assert set(missing) <= set(offered)
    assert len(offered) == SAMPLE_SIZE


def test_a_disliked_favourite_is_still_never_offered(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)

    offered = _offered(
        corpus,
        {"favourite_meals": [{"text": "x", "recipe_id": "rec_007"}], "disliked_ingredients": ["thing7"]},
    )

    assert "rec_007" not in offered


def test_a_liked_cuisine_and_a_protein_minimum_each_reserve_a_few_places(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)

    for seed in (1, 2, 3):
        liked = _offered(corpus, {"cuisines_liked": ["Japanese"]}, seed)
        fish = _offered(corpus, {"protein_targets": [{"protein": "fish", "min_per_week": 2}]}, seed)

        assert len(JAPANESE_FISH & set(liked)) >= pipeline.PROFILE_RESERVE
        assert len(JAPANESE_FISH & set(fish)) >= 2
