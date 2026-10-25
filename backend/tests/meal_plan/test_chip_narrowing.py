"""Chips with a clear rule narrow the offer when the pool can afford it (owner decision 2026-10-25).

Seam: `pipeline.prepare`, over a synthetic corpus with stored answers, read through what it offered. Quick
weeknights uses V5's time-cap rule at 30 minutes; comfort food and guests use their dish-type predicates. A chip
narrows only when at least three fresh recipes per slot pass it; otherwise the offer is left whole and the chip
pays its +2 in the scorer. Hard constraints (dietary decisions, the time cap, meals already planned) apply first
and a chip can never bring back a recipe they ruled out.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime

from glean.meal_plan import pipeline
from glean.meal_plan.dietary_decisions import (
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.meal_plan.schemas import MealPlanRequest
from glean.meal_plan.tools import FeedbackChip, chip_narrows
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer
from glean.recipes.attributes import DishType, RecipeAttributes
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.enrichment.attributes import attribute_questions
from glean.recipes.stored import StoredIngredient, StoredRecipe
from tests.recipes.enrichment.fakes import SNAPSHOT

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)
SLOTS = 2


def _corpus(tmp_path, recipes: dict[str, tuple[int, str | None]]) -> RecipeCorpusStore:
    """`recipes`: id -> (total minutes, dish type or None for unanswered)."""
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for recipe_id, (minutes, _dish) in recipes.items():
        corpus.save(
            StoredRecipe(
                external_id=recipe_id,
                title=f"Dinner {recipe_id}",
                total_time_mins=minutes,
                ingredients=[StoredIngredient(canonical_name=f"thing {recipe_id}", quantity=1, unit="each")],
            )
        )
    question = dict(attribute_questions())["dish_type"]
    summaries = {s.external_id: s for s in corpus.search(per_page=10_000)[0]}
    corpus.save_answers(
        [
            RecipeAnswer(
                recipe_id=recipe_id,
                question=question.name,
                probability=0.95,
                value=dish,
                model=SNAPSHOT,
                content_hash=content_fingerprint(summaries[recipe_id].title, summaries[recipe_id].ingredient_names),
                criteria_hash=question.criteria_hash,
                computed_at=NOW,
            )
            for recipe_id, (_minutes, dish) in recipes.items()
            if dish is not None
        ]
    )
    return corpus


def _request(chips: list[str], **overrides: object) -> MealPlanRequest:
    return MealPlanRequest.model_validate(
        {
            "source": "corpus",
            "pantry": [],
            "purchase_tolerance": 0.5,
            "meals_per_week": SLOTS,
            "dietary_flags": [],
            "max_active_time_mins": None,
            "human_feedback": {"chips": chips, "note": None},
            **overrides,
        }
    )


def _offered(corpus: RecipeCorpusStore, request: MealPlanRequest) -> set[str]:
    return set(pipeline.prepare(request, corpus=corpus, rng=random.Random(0), now=NOW).offered_ids)


def _quick_and_slow(quick: int, slow: int) -> dict[str, tuple[int, str | None]]:
    recipes: dict[str, tuple[int, str | None]] = {f"rec_quick_{i}": (20, None) for i in range(quick)}
    recipes |= {f"rec_slow_{i}": (75, None) for i in range(slow)}
    return recipes


def test_quick_weeknights_uses_the_time_cap_rule_at_thirty_minutes() -> None:
    unknown = RecipeAttributes()
    assert chip_narrows(FeedbackChip.QUICK_WEEKNIGHTS, unknown, total_time_mins=30) is True
    assert chip_narrows(FeedbackChip.QUICK_WEEKNIGHTS, unknown, total_time_mins=31) is False
    # V5's rule: an unknown total time is not evidence the recipe is slow.
    assert chip_narrows(FeedbackChip.QUICK_WEEKNIGHTS, unknown, total_time_mins=None) is True


def test_comfort_food_and_guests_narrow_by_dish_type_and_an_unknown_dish_never_passes() -> None:
    pie = RecipeAttributes(dish_type=DishType.PIE_OR_BAKE)
    salad = RecipeAttributes(dish_type=DishType.SALAD_OR_BOWL)
    assert chip_narrows(FeedbackChip.COMFORT_FOOD, pie, total_time_mins=None) is True
    assert chip_narrows(FeedbackChip.GUESTS, pie, total_time_mins=None) is True
    assert chip_narrows(FeedbackChip.COMFORT_FOOD, salad, total_time_mins=None) is False
    assert chip_narrows(FeedbackChip.COMFORT_FOOD, RecipeAttributes(), total_time_mins=None) is False


def test_quick_weeknights_narrows_the_offer_when_enough_quick_recipes_remain(tmp_path, caplog) -> None:
    corpus = _corpus(tmp_path, _quick_and_slow(quick=6, slow=6))

    with caplog.at_level(logging.INFO):
        offered = _offered(corpus, _request(["quick_weeknights"]))

    assert offered == {f"rec_quick_{i}" for i in range(6)}
    assert any(record.message == "a chip narrowed the offer" for record in caplog.records)


def test_quick_weeknights_falls_back_to_its_score_term_when_too_few_remain(tmp_path, caplog) -> None:
    # Five quick recipes for two slots is fewer than three per slot: the offer stays whole.
    corpus = _corpus(tmp_path, _quick_and_slow(quick=5, slow=6))

    with caplog.at_level(logging.INFO):
        offered = _offered(corpus, _request(["quick_weeknights"]))

    assert any(recipe_id.startswith("rec_slow") for recipe_id in offered)
    assert any(record.message == "a chip fell back to its score term" for record in caplog.records)


def test_without_the_chip_nothing_is_narrowed(tmp_path) -> None:
    corpus = _corpus(tmp_path, _quick_and_slow(quick=6, slow=6))

    assert any(recipe_id.startswith("rec_slow") for recipe_id in _offered(corpus, _request([])))


def test_comfort_food_narrows_to_its_dish_types(tmp_path) -> None:
    recipes: dict[str, tuple[int, str | None]] = {f"rec_pie_{i}": (40, "pie_or_bake") for i in range(3)}
    recipes |= {f"rec_stew_{i}": (40, "soup_or_stew") for i in range(3)}
    recipes |= {f"rec_salad_{i}": (40, "salad_or_bowl") for i in range(4)}
    recipes |= {"rec_unknown": (40, None)}
    corpus = _corpus(tmp_path, recipes)

    offered = _offered(corpus, _request(["comfort_food"]))

    assert offered == {f"rec_pie_{i}" for i in range(3)} | {f"rec_stew_{i}" for i in range(3)}


def test_each_chip_is_decided_on_its_own(tmp_path) -> None:
    # Quick can narrow (6 quick of 12), comfort cannot once quick has (only 2 quick comfort dishes): quick holds,
    # comfort falls back to its score term.
    recipes: dict[str, tuple[int, str | None]] = {f"rec_quick_curry_{i}": (20, "curry") for i in range(2)}
    recipes |= {f"rec_quick_salad_{i}": (20, "salad_or_bowl") for i in range(4)}
    recipes |= {f"rec_slow_curry_{i}": (75, "curry") for i in range(6)}
    corpus = _corpus(tmp_path, recipes)

    offered = _offered(corpus, _request(["quick_weeknights", "comfort_food"]))

    assert offered == {f"rec_quick_curry_{i}" for i in range(2)} | {f"rec_quick_salad_{i}" for i in range(4)}


def test_a_chip_never_brings_back_what_a_hard_constraint_ruled_out(tmp_path) -> None:
    corpus = _corpus(tmp_path, _quick_and_slow(quick=8, slow=4))
    vegan_breaker = "rec_quick_0"
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag="vegan",
                probability=0.99 if recipe_id == vegan_breaker else 0.01,  # the probability it breaks the flag
                model=f"{SNAPSHOT}",
                content_hash=content_fingerprint(summary.title, summary.ingredient_names),
                criteria_hash=question_hash(dietary_questions()["vegan"]),
                computed_at=NOW,
            )
            for summary in corpus.search(per_page=10_000)[0]
            for recipe_id in [summary.external_id]
        ]
    )

    offered = _offered(
        corpus,
        _request(["quick_weeknights"], dietary_flags=["vegan"], exclude_external_ids=["rec_quick_1"]),
    )

    assert vegan_breaker not in offered
    assert "rec_quick_1" not in offered
    assert offered == {f"rec_quick_{i}" for i in range(2, 8)}


def test_narrowing_counts_only_recipes_the_time_cap_allows(tmp_path) -> None:
    # A 15-minute cap leaves the 10-minute dishes alone; quick weeknights then has nothing more to narrow.
    recipes: dict[str, tuple[int, str | None]] = {f"rec_ten_{i}": (10, None) for i in range(6)}
    recipes |= {f"rec_twenty_{i}": (20, None) for i in range(6)}
    corpus = _corpus(tmp_path, recipes)

    offered = _offered(corpus, _request(["quick_weeknights"], max_active_time_mins=15))

    assert offered == {f"rec_ten_{i}" for i in range(6)}
