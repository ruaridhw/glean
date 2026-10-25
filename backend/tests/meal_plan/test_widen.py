"""The pipeline's half of the agent's tools: `tool_context`, `widen` and `plan_drift` (V7).

Seam: the functions the agent's adapters call between a tool and the prepared plan. A filesystem corpus larger
than the sampler's offer stands in for the store, so a recipe the agent finds is one the household was not
offered. They miss the graph that sequences them, which `tests/agent/test_graph.py` covers.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glean.meal_plan import pipeline
from glean.meal_plan.candidates import SAMPLE_SIZE
from glean.meal_plan.schemas import CookedHistoryItem, CorpusMealPlanRecipe, CorpusMealPlanResponse, MealPlanRequest
from glean.meal_plan.tools import RecipeFilter, get_eligible_recipes
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredInstruction, StoredNutrition, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def _corpus(tmp_path: Path, count: int = SAMPLE_SIZE + 5) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for index in range(count):
        corpus.save(
            StoredRecipe(
                external_id=f"rec_{index:02d}",
                title=f"Synthetic dish {index:02d}",
                total_time_mins=30,
                nutrition=StoredNutrition(calories=500 + index),
                ingredients=[
                    StoredIngredient(canonical_name=f"ingredient{index}", quantity=2, unit="g"),
                    StoredIngredient(canonical_name="kale" if index % 2 else "onion", quantity=1, unit="each"),
                ],
                instructions=[StoredInstruction(step_number=1, phase="cook", text="Cook it.")],
            )
        )
    return corpus


def _request(**overrides: object) -> MealPlanRequest:
    values: dict[str, object] = {
        "source": "corpus",
        "pantry": [
            {"id": 1, "name": "kale", "quantity": 1, "unit": "each", "urgency_score": 0.9, "expires_in_days": 2}
        ],
        "purchase_tolerance": 0.3,
        "meals_per_week": 2,
        "dietary_flags": [],
        "max_active_time_mins": None,
    }
    values.update(overrides)
    return MealPlanRequest.model_validate(values)


def test_widen_lets_finalise_keep_a_recipe_the_agent_found(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    request = _request()
    prepared = pipeline.prepare(request, corpus=corpus, rng=random.Random(1), now=NOW)
    ctx = pipeline.tool_context(request, corpus=corpus, now=NOW)
    found = get_eligible_recipes(RecipeFilter(exclude_ids=tuple(prepared.offered_ids)), ctx).recipes
    assert found, "the corpus is larger than the offer, so the agent can find something new"
    new = found[0]

    widened = pipeline.widen(prepared, found, corpus=corpus)

    assert new.recipe_id in widened.offered_ids
    facts = {fact.recipe_id: fact for fact in widened.facts}[new.recipe_id]
    # The scorer's facts for it match a candidate's: its urgent items (the unused-urgent-item row reads them) and
    # no stated calories, which only the lighter chip reads.
    assert facts.urgent_items == tuple(item.name for item in new.urgent_items)
    assert facts.calories_per_serving is None
    assert facts.pantry_fit == new.pantry_fit * (prepared.pantry_fit_scale or 0)
    draft = CorpusMealPlanResponse(
        suggestions=[CorpusMealPlanRecipe(external_id=new.recipe_id, title=new.title, reason="Found it.")]
    )
    result = pipeline.finalise(widened, draft)
    assert [suggestion.external_id for suggestion in result.suggestions] == [new.recipe_id]
    assert pipeline.plan_drift(widened, [new.recipe_id]) is not None
    # The prepared plan the household was offered is untouched: widening returns a copy.
    assert new.recipe_id not in prepared.offered_ids


def test_widen_leaves_offered_and_planned_recipes_alone(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path, count=6)
    request = _request(exclude_external_ids=["rec_00"])
    prepared = pipeline.prepare(request, corpus=corpus, rng=random.Random(1), now=NOW)
    ctx = pipeline.tool_context(request.model_copy(update={"exclude_external_ids": []}), corpus=corpus, now=NOW)

    widened = pipeline.widen(prepared, get_eligible_recipes(RecipeFilter(), ctx).recipes, corpus=corpus)

    assert widened == prepared


def test_tool_context_holds_the_agent_to_the_requests_hard_constraints(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path, count=4)
    request = _request(
        exclude_external_ids=["rec_00"],
        cooked_history=[
            CookedHistoryItem(recipe_id="rec_01", title="Synthetic dish 01", cooked_at=NOW, rating="down", note="never")
        ],
    )

    ctx = pipeline.tool_context(request, corpus=corpus, now=NOW)
    found = [entry.recipe_id for entry in get_eligible_recipes(RecipeFilter(), ctx).recipes]

    assert "rec_00" not in found
    assert "rec_01" not in found
    assert ctx.load_full is not None
    assert ctx.load_full("rec_02") == (("2 g ingredient2", "1 each onion"), ("Cook it.",))
