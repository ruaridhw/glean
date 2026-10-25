"""The pipeline's half of a swap (V10): which meal may replace one slot, and the proposal after it.

Seam: `pipeline.replacement` and `pipeline.with_replacement`, the framework-free rules the agent's swap nodes
call. A prepared plan built by `prepare` over a synthetic corpus stands in for a session's checkpoint. They miss
the graph that asks the model and writes the session, which `tests/agent/test_swap.py` covers.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from glean.meal_plan import balance, pipeline, tools
from glean.meal_plan.schemas import (
    CorpusMealPlanAlternative,
    MealPlanAlternative,
    MealPlanRequest,
    MealPlanResult,
    MealPlanSuggestion,
    ReasonKind,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredNutrition, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


@pytest.fixture
def prepared(tmp_path: Path) -> pipeline.PreparedPlan:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for index in range(12):
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
            )
        )
    request = MealPlanRequest.model_validate(
        {
            "source": "corpus",
            "pantry": [
                {"id": 1, "name": "kale", "quantity": 1, "unit": "each", "urgency_score": 0.9, "expires_in_days": 2}
            ],
            "purchase_tolerance": 0.3,
            "meals_per_week": 3,
            "dietary_flags": [],
            "max_active_time_mins": None,
            "exclude_external_ids": ["rec_11"],
        }
    )
    return pipeline.prepare(request, corpus=corpus, rng=random.Random(1), now=NOW)


def _pick(external_id: str, reason: str = "You asked for something lighter.") -> CorpusMealPlanAlternative:
    return CorpusMealPlanAlternative(
        external_id=external_id,
        title=f"Synthetic dish {external_id[-2:]}",
        reason=reason,
        reason_kind=ReasonKind.FEEDBACK,
    )


def _week(prepared: pipeline.PreparedPlan) -> list[str]:
    return list(prepared.weeks[0].recipe_ids)


def test_the_models_pick_is_kept_with_its_reason_when_the_week_may_use_it(prepared: pipeline.PreparedPlan) -> None:
    week = _week(prepared)
    free = next(external_id for external_id in prepared.offered_ids if external_id not in week)

    chosen = pipeline.replacement(prepared, _pick(free), locked=week[1:], unavailable=set(week))

    assert chosen is not None
    suggestion, degraded = chosen
    assert degraded is False
    assert suggestion.external_id == free
    assert suggestion.reason.startswith("You asked for something lighter.")
    assert suggestion.reason_kind is ReasonKind.FEEDBACK


@pytest.mark.parametrize("which", ["in_the_week", "planned", "invented", "swapped_out"])
def test_a_pick_the_week_may_not_use_falls_back_to_the_scorers_best(
    prepared: pipeline.PreparedPlan, which: str
) -> None:
    week = _week(prepared)
    swapped_out = next(external_id for external_id in prepared.offered_ids if external_id not in week)
    bad = {"in_the_week": week[1], "planned": "rec_11", "invented": "rec_invented", "swapped_out": swapped_out}[which]
    unavailable = {*week, swapped_out}

    chosen = pipeline.replacement(prepared, _pick(bad), locked=week[1:], unavailable=unavailable)

    assert chosen is not None
    suggestion, degraded = chosen
    assert degraded is True
    assert suggestion.external_id not in unavailable | {"rec_11", "rec_invented"}
    assert suggestion.external_id in prepared.offered_ids
    assert suggestion.reason.startswith(pipeline.TEMPLATE_SWAP_REASON)


def test_the_fallback_is_the_candidate_that_scores_best_with_the_locked_meals(prepared: pipeline.PreparedPlan) -> None:
    week = _week(prepared)
    locked = week[1:]
    unavailable = set(week)
    context = balance.scoring_context(prepared.facts)
    free = [external_id for external_id in prepared.offered_ids if external_id not in unavailable]
    best = max(free, key=lambda external_id: tools.score_meal_plan([*locked, external_id], context).total)

    chosen = pipeline.replacement(prepared, None, locked=locked, unavailable=unavailable)

    assert chosen is not None
    assert chosen[0].external_id == best
    assert chosen[1] is True


def test_nothing_left_to_swap_in_is_no_replacement(prepared: pipeline.PreparedPlan) -> None:
    week = _week(prepared)

    assert pipeline.replacement(prepared, None, locked=week[1:], unavailable=set(prepared.offered_ids)) is None


def test_the_replacement_takes_only_its_slot_and_keeps_the_cards_alternative() -> None:
    alternative = MealPlanAlternative(external_id="rec_alt", title="Alt", reason="Instead.")
    base = MealPlanResult(
        week_summary="Two dinners.",
        suggestions=[
            MealPlanSuggestion(external_id="rec_a", title="A", reason="a"),
            MealPlanSuggestion(external_id="rec_b", title="B", reason="b", alternative=alternative),
        ],
    )
    replacement = MealPlanSuggestion(external_id="rec_new", title="New", reason="Fish, as asked.")

    swapped = pipeline.with_replacement(base, 1, replacement)

    assert swapped.suggestions[0] == base.suggestions[0]
    assert swapped.suggestions[1].external_id == "rec_new"
    assert swapped.suggestions[1].alternative == alternative
    assert swapped.week_summary == base.week_summary
    # The alternative itself as the replacement leaves the card nothing else to offer.
    same = pipeline.with_replacement(base, 1, MealPlanSuggestion(external_id="rec_alt", title="Alt", reason="r"))
    assert same.suggestions[1].alternative is None
