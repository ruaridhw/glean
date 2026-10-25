"""The planner's corpus tools: `get_eligible_recipes` and `get_recipes` (spec 6.2, "Tools", V7).

Seam: the two framework-free functions the agent's `act` node, the evals and the MCP server call. A synthetic
corpus of `CorpusRecipe`s stands in for the projection, so these pin the order of the steps (hard constraints,
the six-week floor, the agent's filter, the urgent guarantee, the ranking) without a store or a model. They miss
the adapter that builds the context from the real corpus, which `tests/agent/test_graph.py` covers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from glean.meal_plan.candidates import PantryItem
from glean.meal_plan.eligibility import CookedMeal
from glean.meal_plan.tools import (
    MAX_FILTER_LIMIT,
    CorpusRecipe,
    EligibilityContext,
    FilterRejected,
    Predicate,
    PredicateField,
    PredicateOp,
    RecipeFilter,
    get_eligible_recipes,
    get_recipes,
)
from glean.recipes.attributes import ActiveTimeBucket, Cuisine, MainProtein, RecipeAttributes

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def recipe(
    recipe_id: str,
    *,
    ingredients: tuple[str, ...] = (),
    cuisine: str | None = None,
    protein: MainProtein = MainProtein.UNSURE,
    active: ActiveTimeBucket = ActiveTimeBucket.UNSURE,
    total: int | None = None,
) -> CorpusRecipe:
    return CorpusRecipe(
        recipe_id=recipe_id,
        title=f"Dish {recipe_id}",
        cuisine=cuisine,
        total_time_mins=total,
        ingredient_names=ingredients or (f"thing {recipe_id}",),
        attributes=RecipeAttributes(
            main_protein=protein,
            cuisine=Cuisine(cuisine) if cuisine else Cuisine.UNSURE,
            active_time=active,
        ),
    )


def context(recipes: list[CorpusRecipe], **overrides: object) -> EligibilityContext:
    values: dict[str, object] = {"recipes": tuple(recipes), "slots": 1, "now": NOW}
    values.update(overrides)
    return EligibilityContext(**values)  # ty: ignore[invalid-argument-type]


def ids(result: object) -> list[str]:
    return [entry.recipe_id for entry in result.recipes]  # ty: ignore[unresolved-attribute]


def cooked(recipe_id: str, days_ago: float, rating: str | None = None) -> CookedMeal:
    return CookedMeal(
        title=f"Dish {recipe_id}", recipe_id=recipe_id, cooked_at=NOW - timedelta(days=days_ago), rating=rating
    )


class TestHardConstraints:
    def test_dietary_planned_and_time_cap_are_applied_before_anything_else(self) -> None:
        corpus = [
            recipe("ok"),
            recipe("diet"),
            recipe("planned"),
            recipe("slow", active=ActiveTimeBucket.FROM_45_TO_60),
            recipe("slow-total", total=90),
        ]
        ctx = context(
            corpus,
            dietary_excluded_ids=frozenset({"diet"}),
            planned_ids=frozenset({"planned"}),
            max_active_mins=30,
        )

        assert ids(get_eligible_recipes(RecipeFilter(), ctx)) == ["ok"]

    def test_a_thumbs_down_recipe_never_comes_back_even_when_the_floor_relaxes(self) -> None:
        corpus = [recipe("a"), recipe("b")]
        ctx = context(corpus, slots=3, cooked=(cooked("a", 200, rating="down"),))

        assert ids(get_eligible_recipes(RecipeFilter(), ctx)) == ["b"]


class TestFloor:
    def test_recipes_cooked_in_six_weeks_are_left_out_while_enough_fresh_ones_remain(self) -> None:
        corpus = [recipe(f"r{i}") for i in range(4)]
        ctx = context(corpus, slots=1, cooked=(cooked("r0", 10),))

        result = get_eligible_recipes(RecipeFilter(), ctx)

        assert "r0" not in ids(result)
        assert result.floor_relaxed is False

    def test_a_relaxed_recipe_comes_back_last_carrying_the_recency_penalty(self) -> None:
        corpus = [recipe("old"), recipe("new")]
        ctx = context(corpus, slots=1, cooked=(cooked("old", 10),))

        result = get_eligible_recipes(RecipeFilter(), ctx)

        assert ids(result) == ["new", "old"]
        relaxed = result.recipes[1]
        assert relaxed.offered_after_floor_relaxed is True
        assert relaxed.recency_penalty == -8.0
        assert relaxed.days_since_cooked == pytest.approx(10)
        assert result.recipes[0].recency_penalty == 0.0


class TestFilterNarrows:
    def test_include_and_exclude_predicates_narrow(self) -> None:
        corpus = [
            recipe("fish", protein=MainProtein.FISH),
            recipe("chicken", protein=MainProtein.CHICKEN),
            recipe("beef", protein=MainProtein.BEEF),
        ]
        only_fish_or_beef = Predicate(PredicateField.MAIN_PROTEIN, PredicateOp.IN, ("fish", "beef"))
        not_beef = Predicate(PredicateField.MAIN_PROTEIN, PredicateOp.IN, ("beef",))

        result = get_eligible_recipes(RecipeFilter(include=(only_fish_or_beef,), exclude=(not_beef,)), context(corpus))

        assert ids(result) == ["fish"]

    def test_text_runs_the_corpus_search(self) -> None:
        corpus = [recipe("bibimbap", cuisine="korean"), recipe("lasagne", cuisine="italian")]
        searched: list[str] = []

        def search(text: str) -> set[str]:
            searched.append(text)
            return {"bibimbap"}

        result = get_eligible_recipes(RecipeFilter(text="Korean"), context(corpus, text_search=search))

        assert searched == ["Korean"]
        assert ids(result) == ["bibimbap"]

    def test_text_without_a_search_matches_title_cuisine_and_ingredients(self) -> None:
        corpus = [recipe("a", cuisine="korean"), recipe("b", ingredients=("gochujang",)), recipe("c")]

        assert ids(get_eligible_recipes(RecipeFilter(text="korean"), context(corpus))) == ["a"]
        assert ids(get_eligible_recipes(RecipeFilter(text="gochujang"), context(corpus))) == ["b"]

    def test_uses_pantry_and_exclude_ids_narrow(self) -> None:
        corpus = [recipe("squash", ingredients=("butternut squash", "onion")), recipe("soup", ingredients=("onion",))]
        pantry = (PantryItem(name="butternut squash"), PantryItem(name="onion"))

        result = get_eligible_recipes(RecipeFilter(uses_pantry=("butternut squash",)), context(corpus, pantry=pantry))
        assert ids(result) == ["squash"]

        result = get_eligible_recipes(RecipeFilter(exclude_ids=("squash",)), context(corpus, pantry=pantry))
        assert ids(result) == ["soup"]

    def test_max_active_mins_may_tighten_the_cap(self) -> None:
        corpus = [
            recipe("quick", active=ActiveTimeBucket.UP_TO_15),
            recipe("medium", active=ActiveTimeBucket.FROM_15_TO_30),
        ]

        result = get_eligible_recipes(RecipeFilter(max_active_mins=20), context(corpus, max_active_mins=30))

        assert ids(result) == ["quick"]

    def test_a_filter_that_would_widen_the_time_cap_is_rejected(self) -> None:
        corpus = [
            recipe("quick", active=ActiveTimeBucket.UP_TO_15),
            recipe("slow", active=ActiveTimeBucket.FROM_45_TO_60),
        ]

        with pytest.raises(FilterRejected, match="tighten"):
            get_eligible_recipes(RecipeFilter(max_active_mins=60), context(corpus, max_active_mins=30))

    @pytest.mark.parametrize("limit", [0, MAX_FILTER_LIMIT + 1])
    def test_a_limit_outside_the_allowlist_is_rejected(self, limit: int) -> None:
        with pytest.raises(FilterRejected, match="limit"):
            get_eligible_recipes(RecipeFilter(limit=limit), context([recipe("a")]))

    def test_no_filter_can_bring_back_a_hard_excluded_recipe(self) -> None:
        corpus = [recipe("diet", cuisine="korean")]
        wide_open = RecipeFilter(text="korean", include=(), max_active_mins=None, limit=MAX_FILTER_LIMIT)

        assert ids(get_eligible_recipes(wide_open, context(corpus, dietary_excluded_ids=frozenset({"diet"})))) == []


class TestRanking:
    def test_urgent_recipes_lead_and_survive_the_limit(self) -> None:
        corpus = [
            recipe("staples", ingredients=("onion", "garlic", "rice")),
            recipe("coriander", ingredients=("coriander",)),
            recipe("plain"),
        ]
        pantry = (
            PantryItem(name="onion", urgency_score=1.0),
            PantryItem(name="garlic", urgency_score=1.0),
            PantryItem(name="rice", urgency_score=1.0),
            PantryItem(name="coriander", urgency_score=0.5, expires_in_days=1),
        )

        result = get_eligible_recipes(RecipeFilter(limit=1), context(corpus, pantry=pantry))

        assert ids(result) == ["coriander"]
        assert result.recipes[0].urgent_items == (pantry[3],)
        assert result.matched == 3

    def test_pantry_fit_is_urgency_weighted(self) -> None:
        corpus = [recipe("two-staples", ingredients=("onion", "rice")), recipe("one-urgent", ingredients=("kale",))]
        pantry = (
            PantryItem(name="onion", urgency_score=0.2),
            PantryItem(name="rice", urgency_score=0.2),
            PantryItem(name="kale", urgency_score=0.9),
        )

        result = get_eligible_recipes(RecipeFilter(), context(corpus, pantry=pantry))

        assert ids(result) == ["one-urgent", "two-staples"]
        assert result.recipes[0].pantry_fit == pytest.approx(0.9)
        assert result.recipes[0].pantry_items == ("kale",)

    def test_ties_break_by_the_seed_not_by_input_order(self) -> None:
        corpus = [recipe(f"r{i}") for i in range(12)]

        first = ids(get_eligible_recipes(RecipeFilter(), context(corpus, seed=1)))
        again = ids(get_eligible_recipes(RecipeFilter(), context(list(reversed(corpus)), seed=1)))
        other = ids(get_eligible_recipes(RecipeFilter(), context(corpus, seed=2)))

        assert first == again
        assert first != other

    def test_near_duplicates_are_suppressed(self) -> None:
        shared = ("chicken thigh", "soy sauce", "ginger", "garlic", "rice")
        corpus = [recipe("a", ingredients=shared), recipe("b", ingredients=shared), recipe("c", ingredients=("tofu",))]

        result = get_eligible_recipes(RecipeFilter(), context(corpus))

        assert sorted(ids(result)) in (["a", "c"], ["b", "c"])


class TestGetRecipes:
    def test_summary_carries_the_card_fields_and_names_unknown_ids(self) -> None:
        corpus = [recipe("a", cuisine="korean", total=40, active=ActiveTimeBucket.FROM_15_TO_30)]

        details = get_recipes(["a", "nope"], "summary", context(corpus))

        assert details.unknown == ("nope",)
        (card,) = details.recipes
        assert card.title == "Dish a"
        assert card.active_time_mins == 30
        assert card.attributes.cuisine is Cuisine.KOREAN
        assert card.method == ()

    def test_full_adds_the_ingredient_lines_and_the_method(self) -> None:
        ctx = context(
            [recipe("a")],
            load_full=lambda recipe_id: (("200 g rice",), ("Cook the rice.",)) if recipe_id == "a" else None,
        )

        (card,) = get_recipes(["a"], "full", ctx).recipes

        assert card.ingredients == ("200 g rice",)
        assert card.method == ("Cook the rice.",)
