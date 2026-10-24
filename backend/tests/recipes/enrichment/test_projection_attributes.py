"""The projection carries every recipe's attributes, derived from the answers that still apply.

Seams: `attributes_from_answers` (the derivation), `build_projection` (F1/F2's rebuild path), and the
DynamoDB backend's incremental publishes, which must reach the same document a rebuild would.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glean.decisions import DECISION_MODEL
from glean.recipes.answers import RecipeAnswer, content_fingerprint, dietary_question
from glean.recipes.attributes import ActiveTimeBucket, Cuisine, MainProtein, RecipeAttributes, WholeFood
from glean.recipes.enrichment.active_time import ACTIVE_TIME_ENRICHER
from glean.recipes.enrichment.attributes import ATTRIBUTE_ENRICHER
from glean.recipes.enrichment.dietary import dietary_enrichment_questions
from glean.recipes.enrichment.projection_attributes import attributes_from_answers
from glean.recipes.projection import build_projection
from tests.recipes.corpus_fixtures import synthetic_recipe
from tests.recipes.enrichment.fakes import SNAPSHOT

if TYPE_CHECKING:
    from glean.recipes.enrichment.enricher import EnrichmentQuestion

COMPUTED_AT = datetime(2026, 10, 22, tzinfo=UTC)
TITLE = "Synthetic Bake"
INGREDIENTS = ["rice", "chicken thigh"]
CONTENT = content_fingerprint(TITLE, INGREDIENTS)


def test_a_current_answer_for_every_attribute_reads_back_as_those_attributes() -> None:
    answers = [
        _answer("run", "attribute:main_protein", "chicken"),
        _answer("run", "attribute:main_carb", "rice"),
        _answer("run", "attribute:dish_type", "rice_dish"),
        _answer("run", "attribute:cuisine", "thai"),
        _answer("run", "attribute:whole_food", "mixed"),
        _answer("run", "active_time:bucket", "15-30"),
    ]

    attributes = attributes_from_answers(answers, content_hash=CONTENT)

    assert attributes == RecipeAttributes(
        main_protein=MainProtein.CHICKEN,
        main_carb="rice",
        dish_type="rice_dish",
        cuisine=Cuisine.THAI,
        whole_food=WholeFood.MIXED,
        active_time=ActiveTimeBucket.FROM_15_TO_30,
    )


def test_a_recipe_with_no_attribute_answers_is_unsure_throughout() -> None:
    assert attributes_from_answers([], content_hash=CONTENT) == RecipeAttributes()


def test_a_stored_unsure_reads_back_as_unsure_rather_than_as_no_answer() -> None:
    attributes = attributes_from_answers([_answer("run", "attribute:cuisine", "unsure")], content_hash=CONTENT)

    assert attributes.cuisine is Cuisine.UNSURE


def test_an_answer_to_a_superseded_wording_does_not_reach_the_projection() -> None:
    stale = _answer("run", "attribute:cuisine", "thai", criteria_hash="0" * 64)

    assert attributes_from_answers([stale], content_hash=CONTENT).cuisine is Cuisine.UNSURE


def test_an_answer_from_another_model_does_not_reach_the_projection() -> None:
    stale = _answer("run", "attribute:cuisine", "thai", model="typesafe/jev-1.13-20260917")

    assert attributes_from_answers([stale], content_hash=CONTENT).cuisine is Cuisine.UNSURE


def test_an_answer_about_other_content_does_not_reach_the_projection() -> None:
    stale = _answer("run", "attribute:cuisine", "thai", content_hash="0" * 64)

    assert attributes_from_answers([stale], content_hash=CONTENT).cuisine is Cuisine.UNSURE


def test_a_dietary_answer_carries_no_attribute() -> None:
    dietary = _answer("run", dietary_enrichment_questions()["vegan"].name, "unsure", content_hash=CONTENT)

    assert attributes_from_answers([dietary], content_hash=CONTENT) == RecipeAttributes()


def test_the_rebuild_path_puts_the_attributes_in_the_projection_entry() -> None:
    recipe = synthetic_recipe("rec_x", title=TITLE, ingredients=INGREDIENTS)
    fingerprint = content_fingerprint(recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients])
    answers = [
        _answer("rec_x", "attribute:main_protein", "chicken", content_hash=fingerprint),
        _answer("rec_x", "active_time:bucket", "<=15", content_hash=fingerprint),
    ]

    entry = build_projection([recipe], answers).by_id("rec_x")

    assert entry is not None
    assert entry.recipe_attributes.main_protein is MainProtein.CHICKEN
    assert entry.recipe_attributes.active_time is ActiveTimeBucket.UP_TO_15
    assert entry.recipe_attributes.cuisine is Cuisine.UNSURE


def test_the_rebuild_path_leaves_another_recipes_answers_out_of_this_entry() -> None:
    recipe = synthetic_recipe("rec_x", title=TITLE, ingredients=INGREDIENTS)
    fingerprint = content_fingerprint(recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients])
    other = _answer("rec_other", "attribute:cuisine", "thai", content_hash=fingerprint)

    entry = build_projection([recipe], [other]).by_id("rec_x")

    assert entry is not None
    assert entry.recipe_attributes.cuisine is Cuisine.UNSURE


def _answer(
    recipe_id: str,
    question_name: str,
    value: str | None,
    *,
    content_hash: str = CONTENT,
    criteria_hash: str | None = None,
    model: str = SNAPSHOT,
) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id=recipe_id,
        question=question_name,
        probability=0.86,
        value=value,
        model=model,
        content_hash=content_hash,
        criteria_hash=criteria_hash or _criteria_hash(question_name),
        computed_at=COMPUTED_AT,
    )


def _criteria_hash(name: str) -> str:
    """The current wording's hash for an attribute question; a dietary question is never read for attributes."""
    question: EnrichmentQuestion | None = next(
        (
            question
            for enricher in (ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER)
            for question in enricher.questions()
            if question.name == name
        ),
        None,
    )
    return question.criteria_hash if question is not None else "d" * 64


# A guard on the pinned model the fake reports: an answer under it is current, anything else is stale.
assert DECISION_MODEL in SNAPSHOT
assert dietary_question("vegan") == "dietary:vegan"
