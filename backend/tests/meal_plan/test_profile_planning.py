"""The household profile through the corpus pipeline (V13b): the offer, the agent's tools, a widen and a swap.

Seam: `pipeline.prepare`, `pipeline.tool_context`, `pipeline.widen` and `pipeline.replacement`, the functions the
sync route and the agent graph share. A filesystem corpus where every other recipe uses a disliked ingredient
stands in for the store. They miss the graph that sequences them (`tests/agent/test_graph.py`) and the routes.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from glean.meal_plan import pipeline
from glean.meal_plan.schemas import CorpusMealPlanAlternative, MealPlanRequest
from glean.meal_plan.tools import RecipeFilter, get_eligible_recipes
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)
RECIPES = 40


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for index in range(RECIPES):
        corpus.save(
            StoredRecipe(
                external_id=f"rec_{index:02d}",
                title=f"Synthetic dish {index:02d}",
                total_time_mins=30,
                ingredients=[
                    StoredIngredient(canonical_name=f"ingredient{index}", quantity=2, unit="g"),
                    StoredIngredient(canonical_name="black olives" if index % 2 else "kale", quantity=1, unit="each"),
                ],
            )
        )
    return corpus


def _disliked(recipe_id: str) -> bool:
    return int(recipe_id.removeprefix("rec_")) % 2 == 1


def _request(profile: dict[str, Any] | None = None) -> MealPlanRequest:
    return MealPlanRequest.model_validate(
        {
            "source": "corpus",
            "pantry": [
                {"id": 1, "name": "olives", "quantity": 1, "unit": "jar", "urgency_score": 0.9, "expires_in_days": 1}
            ],
            "purchase_tolerance": 0.3,
            "meals_per_week": 3,
            "dietary_flags": [],
            "max_active_time_mins": None,
            "profile": profile,
        }
    )


DISLIKES_OLIVES = {"disliked_ingredients": ["olive"]}


def test_without_a_profile_the_disliked_recipes_are_offered_as_before(tmp_path: Path) -> None:
    prepared = pipeline.prepare(_request(), corpus=_corpus(tmp_path), rng=random.Random(1), now=NOW)

    assert any(_disliked(recipe_id) for recipe_id in prepared.offered_ids)


def test_the_offer_never_holds_a_recipe_using_a_disliked_ingredient(tmp_path: Path) -> None:
    # Even with the olives about to go off: a dislike beats the urgent guarantee, because it is a hard constraint.
    prepared = pipeline.prepare(_request(DISLIKES_OLIVES), corpus=_corpus(tmp_path), rng=random.Random(1), now=NOW)

    assert prepared.offered_ids
    assert not [recipe_id for recipe_id in prepared.offered_ids if _disliked(recipe_id)]
    assert not [recipe_id for week in prepared.weeks for recipe_id in week.recipe_ids if _disliked(recipe_id)]


def test_the_agents_eligible_recipes_obey_the_dislike_so_a_widen_cannot_add_one(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    request = _request(DISLIKES_OLIVES)
    prepared = pipeline.prepare(request, corpus=corpus, rng=random.Random(1), now=NOW)
    ctx = pipeline.tool_context(request, corpus=corpus, now=NOW)

    found = get_eligible_recipes(RecipeFilter(text="olives"), ctx).recipes
    everything = get_eligible_recipes(RecipeFilter(), ctx).recipes
    widened = pipeline.widen(prepared, everything, corpus=corpus)

    assert found == ()
    assert everything
    assert not [recipe_id for recipe_id in widened.offered_ids if _disliked(recipe_id)]


def test_a_swap_never_brings_in_a_disliked_recipe_even_when_the_model_names_one(tmp_path: Path) -> None:
    prepared = pipeline.prepare(_request(DISLIKES_OLIVES), corpus=_corpus(tmp_path), rng=random.Random(1), now=NOW)
    pick = CorpusMealPlanAlternative(
        external_id="rec_01", title="Synthetic dish 01", reason="Olives!", reason_kind="profile"
    )

    chosen = pipeline.replacement(prepared, pick, locked=prepared.offered_ids[:2], unavailable=set())

    assert chosen is not None
    suggestion, degraded = chosen
    assert degraded is True
    assert not _disliked(suggestion.external_id)
