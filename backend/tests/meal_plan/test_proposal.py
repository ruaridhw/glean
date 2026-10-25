"""The proposal `finalise` writes: week summary, reason kinds, alternatives and the degraded fallback.

The pipeline is exercised for real -- the sampler, the dietary and recency filters, and the reason
writer. Only the model's answer is a value this file writes by hand, because the point is what
`finalise` does with a model's answer, not what a model would say.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from glean.meal_plan import balance, pipeline
from glean.meal_plan.schemas import (
    CorpusMealPlanAlternative,
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    CorpusPlannedAlternative,
    MealPlanRequest,
    MealPlanSuggestion,
    ReasonKind,
)
from glean.meal_plan.tools import LIGHTER_CHIP, Rating, Term, score_meal_plan
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.enrichment.active_time import active_time_question
from glean.recipes.enrichment.attributes import attribute_questions
from glean.recipes.enrichment.enricher import MIN_ATTRIBUTE_BAR
from glean.recipes.stored import StoredIngredient, StoredNutrition, StoredRecipe
from glean.sessions.models import MAX_ITEM_BYTES, RESULT_RESERVE_BYTES, item_bytes, stored_input_bytes
from tests.recipes.enrichment.fakes import SNAPSHOT

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 4, 7, 12, tzinfo=UTC)
LOCAL_DATE = date(2026, 4, 8)
MEALS = 2

RECIPES = {
    "rec_coriander_chicken": ("Coriander Chicken", ["chicken breast", "coriander"]),
    "rec_lentil_bake": ("Lentil Bake", ["lentils", "potato"]),
    "rec_tofu_noodles": ("Tofu Noodles", ["tofu", "noodles"]),
    "rec_chickpea_curry": ("Chickpea Curry", ["chickpeas", "coconut milk"]),
    "rec_fish_pie": ("Fish Pie", ["haddock", "potato"]),
    "rec_bean_chilli": ("Bean Chilli", ["kidney beans", "rice"]),
    "rec_slow_roast": ("Slow Roast", ["beef shin", "carrot"]),
}
# One recipe is too slow for a 30-minute cap, so it is eligible only when the cap allows it.
SLOW = "rec_slow_roast"
TIME_CAP_MINS = 30
SLOW_TOTAL_MINS = 90


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, (title, ingredients) in RECIPES.items():
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
                total_time_mins=SLOW_TOTAL_MINS if external_id == SLOW else 20,
            )
        )
    return corpus


def _request(**overrides: object) -> MealPlanRequest:
    return MealPlanRequest(
        **{
            "source": "corpus",
            "pantry": [],
            "purchase_tolerance": 0.3,
            "meals_per_week": MEALS,
            "local_date": LOCAL_DATE,
            "dietary_flags": [],
            "max_active_time_mins": None,
            **overrides,
        }
    )


def _prepared(tmp_path: Path, **overrides: object) -> pipeline.PreparedPlan:
    return pipeline.prepare(_request(**overrides), corpus=_corpus(tmp_path), rng=random.Random(0), now=NOW)


def _pick(prepared: pipeline.PreparedPlan, index: int, **overrides: object) -> CorpusMealPlanRecipe:
    external_id = prepared.offered_ids[index]
    return CorpusMealPlanRecipe(
        **{
            "external_id": external_id,
            "title": prepared.titles[external_id],
            "reason": "A good fit for the week.",
            "reason_kind": ReasonKind.BALANCE,
            **overrides,
        }
    )


def _alternative(prepared: pipeline.PreparedPlan, index: int, **overrides: object) -> CorpusMealPlanAlternative:
    external_id = prepared.offered_ids[index]
    return CorpusMealPlanAlternative(
        **{
            "external_id": external_id,
            "title": prepared.titles[external_id],
            "reason": "Also worth cooking.",
            "reason_kind": ReasonKind.PROFILE,
            **overrides,
        }
    )


def _draft(
    prepared: pipeline.PreparedPlan,
    *,
    summary: str = "Two easy dinners.",
    suggestions: list[CorpusMealPlanRecipe] | None = None,
    planned: list[CorpusPlannedAlternative] | None = None,
) -> CorpusMealPlanResponse:
    return CorpusMealPlanResponse(
        week_summary=summary,
        suggestions=suggestions if suggestions is not None else [_pick(prepared, 0), _pick(prepared, 1)],
        planned_alternatives=planned or [],
    )


def test_a_proposal_carries_the_contract_shape(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    result = pipeline.finalise(prepared, _draft(prepared))
    dumped = result.model_dump(mode="json")

    assert set(dumped) == {"suggestions", "week_summary", "planned_alternatives", "degraded"}
    assert dumped["week_summary"] == "Two easy dinners."
    assert dumped["degraded"] is False
    assert set(dumped["suggestions"][0]) == {
        "recipe_id",
        "external_id",
        "title",
        "reason",
        "missing_ingredients",
        "uses_up",
        "reason_kind",
        "alternative",
        "attributes",
    }
    # The labels a card shows are additive: four fields, all nullable.
    assert set(dumped["suggestions"][0]["attributes"]) == {
        "main_protein",
        "main_carb",
        "dish_type",
        "active_time_mins",
    }
    # An alternative is a suggestion that carries no alternative of its own.
    assert set(dumped["suggestions"][0]["alternative"]) == {
        "recipe_id",
        "external_id",
        "title",
        "reason",
        "missing_ingredients",
        "uses_up",
        "reason_kind",
        "attributes",
    }


def test_a_card_labels_the_recipe_from_its_measured_attributes(tmp_path: Path) -> None:
    """Protein, carb, dish type and the active-time upper bound: what V3's card shows (spec 6.5)."""
    corpus = _corpus(tmp_path)
    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    chosen = prepared.offered_ids[0]
    _enrich(
        corpus,
        chosen,
        main_protein="chicken",
        main_carb="rice",
        dish_type="curry",
        active_time="<=15",
    )

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)])).suggestions[0]

    assert suggestion.attributes.model_dump() == {
        "main_protein": "chicken",
        "main_carb": "rice",
        "dish_type": "curry",
        "active_time_mins": 15,
    }


def test_an_unsure_attribute_is_left_out_rather_than_invented(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    chosen = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW).offered_ids[0]
    # The model was not confident enough: the answer is `unsure`, which is not a label.
    _enrich(corpus, chosen, main_protein="unsure", main_carb="rice")

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)])).suggestions[0]

    assert suggestion.attributes.main_protein is None
    assert suggestion.attributes.main_carb == "rice"


def test_a_recipe_with_no_answers_labels_only_its_total_time(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)])).suggestions[0]

    assert suggestion.attributes.model_dump() == {
        "main_protein": None,
        "main_carb": None,
        "dish_type": None,
        "active_time_mins": 20,  # the corpus fixture's total time; no bucket was measured
    }


def test_the_card_never_shows_more_hands_on_minutes_than_the_recipe_takes(tmp_path: Path) -> None:
    """A 30-45 bucket on a 35-minute recipe is a 35-minute recipe, not a 45-minute one."""
    corpus = _corpus(tmp_path)
    corpus.save(
        StoredRecipe(
            external_id="rec_quick_ish",
            title="Quick-ish Bake",
            ingredients=[StoredIngredient(canonical_name="haddock", quantity=1, unit="each")],
            total_time_mins=35,
        )
    )
    _enrich(corpus, "rec_quick_ish", active_time="30-45")

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    index = prepared.offered_ids.index("rec_quick_ish")
    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, index)])).suggestions[0]

    assert suggestion.attributes.active_time_mins == 35


def test_a_sixty_plus_bucket_has_no_upper_bound_so_the_card_shows_total_time(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    chosen = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW).offered_ids[0]
    _enrich(corpus, chosen, active_time="60+")

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)])).suggestions[0]

    assert suggestion.attributes.active_time_mins == 20


def test_an_alternative_carries_its_own_labels_for_the_swap_panel(tmp_path: Path) -> None:
    """ "Also fish, 25 min": the panel labels the alternative, not the meal it would replace."""
    corpus = _corpus(tmp_path)
    first = pipeline.prepare(_request(meals_per_week=1), corpus=corpus, rng=random.Random(0), now=NOW)
    chosen, swap_id = first.weeks[0].recipe_ids[0], first.weeks[1].recipe_ids[0]
    assert swap_id != chosen
    _enrich(corpus, swap_id, main_protein="fish", active_time="<=15")

    prepared = pipeline.prepare(_request(meals_per_week=1), corpus=corpus, rng=random.Random(0), now=NOW)
    assert prepared.weeks[0].recipe_ids == [chosen]
    result = pipeline.finalise(
        prepared,
        CorpusMealPlanResponse(
            week_summary="One dinner.",
            chosen_week=0,
            suggestions=[
                CorpusMealPlanRecipe(external_id=chosen, title=prepared.titles[chosen], reason="The scorer's pick.")
            ],
        ),
    )
    swap = result.suggestions[0].alternative

    assert swap is not None
    assert swap.external_id == swap_id
    assert (swap.attributes.main_protein, swap.attributes.active_time_mins) == ("fish", 15)


def test_a_card_without_an_alternative_is_offered_the_other_weeks_meal(tmp_path: Path) -> None:
    # The other candidate week is balanced as a whole, so its meal in the same slot is a better swap than a
    # spare candidate from the end of the offer.
    prepared = _prepared(tmp_path, meals_per_week=2)
    week = prepared.weeks[0].recipe_ids
    targets = balance.swap_targets(prepared.weeks, week)

    result = pipeline.finalise(prepared, _week_draft(prepared, 0))
    alternatives = [suggestion.alternative for suggestion in result.suggestions]

    assert targets, "the fixture's two weeks have to differ somewhere for this to test anything"
    assert all(alternative is not None for alternative in alternatives)
    for position, target in targets.items():
        assert alternatives[position] is not None
        assert alternatives[position].external_id == target
    assert not set(week) & {alternative.external_id for alternative in alternatives if alternative}


def test_a_payload_without_attributes_still_reads(tmp_path: Path) -> None:
    """Additive wire change: a proposal written before V5 (or a checkpoint) reads with empty labels."""
    suggestion = MealPlanSuggestion.model_validate({"external_id": "rec_x", "title": "X", "reason": "Why."})

    assert suggestion.attributes.model_dump() == dict.fromkeys(
        ["main_protein", "main_carb", "dish_type", "active_time_mins"]
    )


def test_a_planned_meal_alternative_is_a_suggestion_with_no_alternative_of_its_own(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path, exclude_external_ids=["rec_lentil_bake"])

    result = pipeline.finalise(prepared, _draft(prepared))
    dumped = result.model_dump(mode="json")

    assert [entry["external_id"] for entry in dumped["planned_alternatives"]] == ["rec_lentil_bake"]
    assert dumped["planned_alternatives"][0]["alternative"]["alternative"] is None


def test_the_models_reason_kinds_reach_the_proposal(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    picks = [_pick(prepared, 0, reason_kind=ReasonKind.HISTORY), _pick(prepared, 1, reason_kind=ReasonKind.URGENT_ITEM)]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks))

    assert [suggestion.reason_kind for suggestion in result.suggestions] == [
        ReasonKind.HISTORY,
        ReasonKind.URGENT_ITEM,
    ]
    assert result.model_dump(mode="json")["suggestions"][0]["reason_kind"] == "history"


def test_each_slot_gets_an_alternative_from_the_candidates_it_was_offered(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    picks = [_pick(prepared, 0, alternative=_alternative(prepared, 2)), _pick(prepared, 1)]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks))
    first, second = result.suggestions

    assert first.alternative is not None
    assert first.alternative.external_id == prepared.offered_ids[2]
    # The model gave the second slot no alternative, so the server took the next-best candidate.
    assert second.alternative is not None
    assert second.alternative.external_id not in {
        first.external_id,
        second.external_id,
        first.alternative.external_id,
    }


def test_an_alternative_never_repeats_a_chosen_meal_or_another_alternative(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path, meals_per_week=3)
    picks = [
        _pick(prepared, 0, alternative=_alternative(prepared, 0)),  # its own meal
        _pick(prepared, 1, alternative=_alternative(prepared, 2)),  # also slot 3's alternative below
        _pick(prepared, 2, alternative=_alternative(prepared, 2)),
    ]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks))

    alternatives = [suggestion.alternative.external_id for suggestion in result.suggestions if suggestion.alternative]
    chosen = {suggestion.external_id for suggestion in result.suggestions}
    assert len(alternatives) == len(set(alternatives))
    assert not chosen & set(alternatives)
    assert alternatives[0] != prepared.offered_ids[0]


def test_an_alternative_that_was_not_offered_is_dropped_rather_than_failing_the_plan(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    invented = CorpusMealPlanAlternative(external_id="rec_invented", title="Invented", reason="Nope.")

    result = pipeline.finalise(
        prepared,
        _draft(prepared, suggestions=[_pick(prepared, 0, alternative=invented), _pick(prepared, 1)]),
    )

    alternative = result.suggestions[0].alternative
    assert len(result.suggestions) == MEALS
    assert alternative is not None
    assert alternative.external_id in prepared.offered_ids


def test_a_slot_with_no_spare_candidate_has_no_alternative(tmp_path: Path) -> None:
    # Only two recipes are eligible, so both fill the week and nothing is left to offer as a swap.
    prepared = _prepared(
        tmp_path,
        exclude_external_ids=[
            "rec_coriander_chicken",
            "rec_tofu_noodles",
            "rec_chickpea_curry",
            "rec_fish_pie",
            "rec_bean_chilli",
        ],
    )
    assert len(prepared.offered_ids) == MEALS
    picks = [_pick(prepared, 0, alternative=None), _pick(prepared, 1, alternative=None)]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks))

    assert [suggestion.alternative for suggestion in result.suggestions] == [None, None]


def test_a_planned_corpus_meal_gets_an_alternative(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path, exclude_external_ids=["rec_lentil_bake"])
    picks = [
        _pick(prepared, 0, alternative=_alternative(prepared, 3)),
        _pick(prepared, 1, alternative=_alternative(prepared, 4)),
    ]
    planned = [
        CorpusPlannedAlternative(planned_external_id="rec_lentil_bake", alternative=_alternative(prepared, 2)),
    ]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks, planned=planned))

    assert [entry.external_id for entry in result.planned_alternatives] == ["rec_lentil_bake"]
    assert result.planned_alternatives[0].alternative.external_id == prepared.offered_ids[2]


def test_a_planned_meal_that_is_not_in_the_corpus_gets_no_alternative(tmp_path: Path) -> None:
    # The app's own plan entry may not be a corpus recipe, so there is nothing to swap it to.
    prepared = _prepared(tmp_path, exclude_external_ids=["rec_from_the_app"])
    planned = [
        CorpusPlannedAlternative(planned_external_id="rec_from_the_app", alternative=_alternative(prepared, 2)),
    ]

    result = pipeline.finalise(prepared, _draft(prepared, planned=planned))

    assert result.planned_alternatives == []


def test_a_planned_meal_is_never_offered_as_an_alternative_to_a_slot(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path, exclude_external_ids=["rec_lentil_bake"])
    planned = [
        CorpusPlannedAlternative(
            planned_external_id="rec_lentil_bake",
            alternative=CorpusMealPlanAlternative(external_id="rec_lentil_bake", title="Lentil Bake", reason="No."),
        )
    ]

    result = pipeline.finalise(prepared, _draft(prepared, planned=planned))

    assert result.planned_alternatives[0].alternative.external_id != "rec_lentil_bake"
    assert all(suggestion.alternative is not None for suggestion in result.suggestions)
    assert "rec_lentil_bake" not in {
        suggestion.alternative.external_id for suggestion in result.suggestions if suggestion.alternative
    }


def test_a_blank_week_summary_falls_back_to_template_text(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    result = pipeline.finalise(prepared, _draft(prepared, summary="   "))

    assert result.week_summary == "2 dinners for this week."


def test_the_week_summary_is_always_one_line(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    result = pipeline.finalise(prepared, _draft(prepared, summary=" Fish twice.\nAnd the coriander\ngets used. "))

    assert result.week_summary == "Fish twice. And the coriander gets used."


def test_the_degraded_fallback_fills_every_field_from_template_text(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path, exclude_external_ids=["rec_lentil_bake"])

    result = pipeline.degraded(prepared)

    assert result.degraded is True
    assert result.week_summary == "2 dinners for this week."
    # The fallback is the scorer's best week, not the sampler's first N: a degraded run still gets balance.
    assert [suggestion.external_id for suggestion in result.suggestions] == prepared.weeks[0].recipe_ids
    assert all(suggestion.reason for suggestion in result.suggestions)
    assert all(suggestion.reason_kind in set(ReasonKind) for suggestion in result.suggestions)
    # Every field a proposal carries is filled: a degraded week has alternatives like any other.
    assert all(suggestion.alternative is not None for suggestion in result.suggestions)
    assert [entry.external_id for entry in result.planned_alternatives] == ["rec_lentil_bake"]


def test_the_degraded_fallback_still_names_the_urgent_item_it_uses(tmp_path: Path) -> None:
    prepared = _prepared(
        tmp_path,
        pantry=[
            {
                "id": 1,
                "name": "coriander",
                "quantity": 50,
                "unit": "g",
                "urgency_score": 150.0,
                "expires_in_days": 2,
            }
        ],
    )

    result = pipeline.degraded(prepared)

    herby = next(suggestion for suggestion in result.suggestions if suggestion.external_id == "rec_coriander_chicken")
    assert herby.reason_kind is ReasonKind.URGENT_ITEM
    assert "Uses up your coriander (goes off Fri)." in herby.reason
    assert [item.name for item in herby.uses_up] == ["coriander"]


def test_an_alternative_must_be_eligible_not_merely_named(tmp_path: Path) -> None:
    # The time cap kept the slow roast out of the candidates, so nothing may offer it as a swap.
    prepared = _prepared(tmp_path, max_active_time_mins=TIME_CAP_MINS)
    assert SLOW not in prepared.offered_ids
    named = CorpusMealPlanAlternative(external_id=SLOW, title="Slow Roast", reason="Roast it.")
    picks = [_pick(prepared, 0, alternative=named), _pick(prepared, 1)]

    result = pipeline.finalise(prepared, _draft(prepared, suggestions=picks))

    alternatives = [suggestion.alternative for suggestion in result.suggestions]
    assert all(alternative is not None for alternative in alternatives)
    assert SLOW not in {alternative.external_id for alternative in alternatives if alternative}


def _wide_corpus(tmp_path: Path, count: int) -> RecipeCorpusStore:
    """*count* recipes that share no ingredients, so none suppresses another as a near-duplicate."""
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for index in range(count):
        corpus.save(
            StoredRecipe(
                external_id=f"rec_wide_{index:02d}",
                title=f"Wide Dish {index}",
                ingredients=[
                    StoredIngredient(canonical_name=f"ingredient {index} alpha", quantity=1, unit="each"),
                    StoredIngredient(canonical_name=f"ingredient {index} beta", quantity=1, unit="each"),
                ],
                total_time_mins=20,
            )
        )
    return corpus


def test_the_largest_proposal_fits_the_result_reserve(tmp_path: Path) -> None:
    """V1 reserves 64 KB of the session item for the plan (`RESULT_RESERVE_BYTES`), sized for V3.

    The biggest proposal V3 can produce: seven meals, an alternative per card, an alternative per
    planned meal, and long prose in every reason. It must fit, or an accepted request would end
    `failed / model_error` on the write instead of showing the week.
    """
    planned_ids = [f"rec_wide_{index:02d}" for index in range(7)]
    prepared = pipeline.prepare(
        _request(meals_per_week=7, exclude_external_ids=planned_ids),
        corpus=_wide_corpus(tmp_path, count=28),
        rng=random.Random(0),
        now=NOW,
    )
    assert len(prepared.offered_ids) == 21
    prose = ("A long but plausible sentence about the week, the pantry and what is going off soon. " * 16)[:1200]
    picks = [
        _pick(prepared, index, reason=prose, alternative=_alternative(prepared, 7 + index, reason=prose))
        for index in range(7)
    ]
    planned = [
        CorpusPlannedAlternative(
            planned_external_id=external_id, alternative=_alternative(prepared, 14 + index, reason=prose)
        )
        for index, external_id in enumerate(planned_ids)
    ]

    result = pipeline.finalise(prepared, _draft(prepared, summary=prose[:400], suggestions=picks, planned=planned))

    assert len(result.suggestions) == 7
    assert all(suggestion.alternative is not None for suggestion in result.suggestions)
    assert len(result.planned_alternatives) == 7
    payload = result.model_dump_json()
    # A genuinely large proposal: 21 reasons of 1,200 characters each.
    assert len(payload.encode()) > 20_000
    assert len(payload.encode()) < RESULT_RESERVE_BYTES
    # And the whole item still fits, with the request's stored inputs and three progress lines.
    assert (
        item_bytes(
            inputs=stored_input_bytes(_request(meals_per_week=7, exclude_external_ids=planned_ids)),
            progress=[prose[:200]] * 3,
            result=payload,
        )
        < MAX_ITEM_BYTES
    )


def _enrich(corpus: RecipeCorpusStore, recipe_id: str, **labels: str) -> None:
    """Store current answers for one recipe, as an enrichment run at the floor bar would.

    `labels` names the attributes to answer (`main_protein="chicken"`, `active_time="15-30"`); the value is
    what the attribute stores, including `unsure`.
    """
    summary = next(entry for entry in corpus.search(per_page=10_000)[0] if entry.external_id == recipe_id)
    questions = dict(attribute_questions())
    questions["active_time"] = active_time_question(MIN_ATTRIBUTE_BAR)
    answers = []
    for attribute, value in labels.items():
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


# --- V6: the scorer's inputs and the two weeks the model picks between ------------------------------------


def test_prepare_builds_the_scorers_inputs_from_the_offer(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    first = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    herby = "rec_coriander_chicken"
    _enrich(corpus, herby, main_protein="chicken", main_carb="rice", whole_food="whole")
    prepared = pipeline.prepare(
        _request(
            pantry=[{"id": 1, "name": "coriander", "quantity": 50, "unit": "g", "urgency_score": 150.0}],
            cooked_history=[
                {
                    "recipe_id": "rec_lentil_bake",
                    "title": "Lentil Bake",
                    "cooked_at": (NOW - timedelta(days=60)).isoformat(),
                    "rating": "up",
                }
            ],
        ),
        corpus=corpus,
        rng=random.Random(0),
        now=NOW,
    )

    assert [fact.recipe_id for fact in prepared.facts] == prepared.offered_ids
    facts = {fact.recipe_id: fact for fact in prepared.facts}
    # The pantry fit is scaled so the offer's strongest match is worth about +3, as the scorer's row says.
    assert facts[herby].pantry_fit == 3.0
    assert max(fact.pantry_fit for fact in prepared.facts) == 3.0
    assert facts[herby].attributes["main_protein"] == "chicken"
    assert facts[herby].attributes["main_carb"] == "rice"
    assert facts[herby].attributes["whole_food"] == "whole"
    # A recipe nothing has measured reads as unsure, so it earns no variety credit and no penalty.
    assert facts["rec_tofu_noodles"].attributes["main_protein"] == "unsure"
    # The history's age and thumb reach the scorer without it re-deciding the floor.
    assert facts["rec_lentil_bake"].days_since_cooked == pytest.approx(60.0)
    assert facts["rec_lentil_bake"].rating == Rating.UP
    assert not any(fact.offered_after_floor_relaxed for fact in prepared.facts)
    assert first.offered_ids != []  # the offer is unchanged by enriching and by the history


def test_prepare_offers_two_weeks_of_the_weeks_size(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    offered = set(prepared.offered_ids)

    assert len(prepared.weeks) == 2
    assert all(len(week.recipe_ids) == MEALS for week in prepared.weeks)
    assert all(set(week.recipe_ids) <= offered for week in prepared.weeks)
    assert set(prepared.weeks[0].recipe_ids) != set(prepared.weeks[1].recipe_ids)
    assert prepared.weeks[0].total >= prepared.weeks[1].total


def test_the_model_is_given_the_two_weeks_with_the_rows_that_scored_them(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    message = json.loads(prepared.user)

    assert [week["index"] for week in message["candidate_weeks"]] == [0, 1]
    first = message["candidate_weeks"][0]
    assert [meal["external_id"] for meal in first["meals"]] == prepared.weeks[0].recipe_ids
    assert first["meals"][0]["title"] == prepared.titles[prepared.weeks[0].recipe_ids[0]]
    assert first["score"] == round(prepared.weeks[0].total, 2)
    # The prompt still carries every candidate, because an alternative may be any of them.
    assert {candidate["external_id"] for candidate in message["candidates"]} == set(prepared.offered_ids)


def test_stated_calories_are_read_only_when_the_lighter_chip_is_on(tmp_path: Path) -> None:
    # No request can select a chip until V9, and calories are the one input only the lighter term reads, so a
    # Generate must not pay up to 25 recipe reads for it. Today's prepare therefore reads none of them.
    corpus = _corpus(tmp_path)
    first = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    fed = first.offered_ids[0]
    stored = corpus.get(fed)
    assert stored is not None
    corpus.save(stored.model_copy(update={"nutrition": StoredNutrition(calories=640, protein_g=30)}))

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    with_chip = pipeline._stated_calories(corpus, [fed, first.offered_ids[1]], chips=frozenset({LIGHTER_CHIP}))

    assert {fact.recipe_id: fact.calories_per_serving for fact in prepared.facts}[fed] is None
    assert with_chip == {fed: 640, first.offered_ids[1]: None}


def test_a_recipe_whose_calories_cannot_be_read_is_unknown_rather_than_a_failed_generate(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    first = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    unreadable, readable = first.offered_ids[0], first.offered_ids[1]
    stored = corpus.get(readable)
    assert stored is not None
    corpus.save(stored.model_copy(update={"nutrition": StoredNutrition(calories=520)}))
    original_get = corpus.get

    def get(external_id: str):
        if external_id == unreadable:
            raise ConnectionError("the blob store went away")
        return original_get(external_id)

    corpus.get = get  # type: ignore[method-assign]
    calories = pipeline._stated_calories(corpus, [unreadable, readable], chips=frozenset({LIGHTER_CHIP}))

    assert calories == {unreadable: None, readable: 520}


def _week_draft(prepared: pipeline.PreparedPlan, index: int, **overrides: object) -> CorpusMealPlanResponse:
    """The model answering with one of the two candidate weeks, as the prompt asks it to."""
    week = prepared.weeks[index]
    return CorpusMealPlanResponse(
        week_summary="A balanced week.",
        chosen_week=index,
        suggestions=[
            CorpusMealPlanRecipe(
                external_id=external_id,
                title=prepared.titles.get(external_id, external_id),
                reason="Works for this week.",
                reason_kind=ReasonKind.BALANCE,
            )
            for external_id in week.recipe_ids
        ],
        **overrides,  # type: ignore[arg-type]
    )


def test_either_candidate_week_is_a_valid_pick(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    prepared = _prepared(tmp_path)

    for index in (0, 1):
        result = pipeline.finalise(prepared, _week_draft(prepared, index))
        assert [suggestion.external_id for suggestion in result.suggestions] == prepared.weeks[index].recipe_ids

    drifts = [record for record in caplog.records if record.message == "meal plan drift from the scorer's best week"]
    assert len(drifts) == 2
    assert drifts[0].__dict__["chosen_week"] == 0
    assert drifts[0].__dict__["week_matches"] is True
    assert drifts[1].__dict__["chosen_week"] == 1
    assert drifts[1].__dict__["gap"] >= 0


def test_a_week_the_scorer_did_not_offer_is_kept_and_measured(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # A model that composes its own week instead of taking one of the two: the pick stands, and the gap is what
    # the eval reads as drift. Nothing about the week's validity changes, only what the log records.
    prepared = _prepared(tmp_path, meals_per_week=2)
    in_either_week = set(prepared.weeks[0].recipe_ids) | set(prepared.weeks[1].recipe_ids)
    outside = next(external_id for external_id in prepared.offered_ids if external_id not in in_either_week)
    composed = [prepared.weeks[0].recipe_ids[0], outside]

    result = pipeline.finalise(
        prepared,
        CorpusMealPlanResponse(
            week_summary="Two dinners.",
            suggestions=[
                CorpusMealPlanRecipe(
                    external_id=external_id,
                    title=prepared.titles.get(external_id, external_id),
                    reason="Composed by the model.",
                    reason_kind=ReasonKind.BALANCE,
                )
                for external_id in composed
            ],
        ),
    )

    assert [suggestion.external_id for suggestion in result.suggestions] == composed
    drift = next(record for record in caplog.records if record.message == "meal plan drift from the scorer's best week")
    assert drift.__dict__["chosen_week"] is None
    assert drift.__dict__["week_matches"] is None
    assert drift.__dict__["gap"] >= 0


def test_a_model_that_names_one_week_and_returns_another_keeps_its_meals(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Judgement, not validity: `finalise` keeps what the model returned and records the disagreement.
    prepared = _prepared(tmp_path)
    draft = _week_draft(prepared, 1).model_copy(update={"chosen_week": 0})

    result = pipeline.finalise(prepared, draft)

    assert [suggestion.external_id for suggestion in result.suggestions] == prepared.weeks[1].recipe_ids
    warnings = [record for record in caplog.records if "named one candidate week" in record.message]
    assert len(warnings) == 1


def test_a_model_naming_a_week_that_does_not_exist_is_kept_and_flagged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    prepared = _prepared(tmp_path)

    result = pipeline.finalise(prepared, _week_draft(prepared, 0).model_copy(update={"chosen_week": 7}))

    assert len(result.suggestions) == MEALS
    errors = [record for record in caplog.records if "not offered" in record.message]
    assert len(errors) == 1
    # A week index that does not exist cannot also be "a week the model did not return": one line, not two.
    assert not [record for record in caplog.records if "named one candidate week" in record.message]


def test_a_plan_checkpointed_before_v6_still_finalises(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # A session checkpointed before V6 carries a prepared plan with no facts and no weeks: it must resume as it
    # did then, not fail on the fields it never had.
    prepared = _prepared(tmp_path)
    legacy = {key: value for key, value in prepared.model_dump(mode="json").items() if key not in {"facts", "weeks"}}

    resumed = pipeline.PreparedPlan.model_validate(legacy)
    result = pipeline.finalise(resumed, _draft(resumed))

    assert [suggestion.external_id for suggestion in result.suggestions] == resumed.offered_ids[:MEALS]
    assert [record for record in caplog.records if record.message.startswith("meal plan drift")] == []


def test_the_fallback_is_the_scorers_best_week_with_no_drift(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # A run that falls back still gets a balanced week, and the log records no drift: the server took the
    # scorer's own pick, so there is nothing to measure it against.
    prepared = _prepared(tmp_path, meals_per_week=3)

    result = pipeline.degraded(prepared)

    assert [suggestion.external_id for suggestion in result.suggestions] == prepared.weeks[0].recipe_ids
    drift = next(record for record in caplog.records if record.message == "meal plan drift from the scorer's best week")
    assert drift.__dict__["gap"] == 0.0
    assert drift.__dict__["chosen_week"] is None


def test_a_checkpoint_from_before_v6_falls_back_to_the_samplers_order(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    legacy = {key: value for key, value in prepared.model_dump(mode="json").items() if key not in {"facts", "weeks"}}

    result = pipeline.degraded(pipeline.PreparedPlan.model_validate(legacy))

    assert [suggestion.external_id for suggestion in result.suggestions] == prepared.offered_ids[:MEALS]


def test_a_recipe_the_floor_relaxed_is_not_offered_as_a_swap(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # A relaxed recipe is a fallback for a tight week, not a suggestion: it is recently cooked, so offering it
    # as "cook this instead" is exactly the repeat the floor exists to avoid.
    corpus = _corpus(tmp_path)
    first = pipeline.prepare(_request(meals_per_week=2), corpus=corpus, rng=random.Random(0), now=NOW)
    relaxed_id = first.offered_ids[0]
    # A history that mentions one offered recipe: it is then only offered because the floor gave way.
    prepared = pipeline.prepare(
        _request(
            meals_per_week=2,
            exclude_external_ids=[external_id for external_id in first.offered_ids if external_id != relaxed_id],
            cooked_history=[
                {
                    "recipe_id": relaxed_id,
                    "title": first.titles[relaxed_id],
                    "cooked_at": (NOW - timedelta(days=3)).isoformat(),
                    "rating": None,
                }
            ],
        ),
        corpus=corpus,
        rng=random.Random(0),
        now=NOW,
    )
    facts = {fact.recipe_id: fact for fact in prepared.facts}

    assert facts[relaxed_id].offered_after_floor_relaxed is True
    result = pipeline.finalise(prepared, _week_draft(prepared, 0))
    offered_as_swap = {
        suggestion.alternative.external_id for suggestion in result.suggestions if suggestion.alternative
    }

    assert relaxed_id not in offered_as_swap


def test_a_relaxed_recipe_that_only_the_other_week_has_is_never_a_swap(tmp_path: Path) -> None:
    # The reviewer's case: the other candidate week differs only by a recipe the six-week floor relaxed back in.
    # It is the swap the scorer would suggest and exactly the one a card must not offer while fresh spares exist.
    prepared = _prepared(tmp_path, meals_per_week=2)
    fresh_a, fresh_b, relaxed = prepared.offered_ids[0], prepared.offered_ids[1], prepared.offered_ids[2]
    prepared = prepared.model_copy(
        update={
            "facts": [
                fact.model_copy(update={"offered_after_floor_relaxed": fact.recipe_id == relaxed})
                for fact in prepared.facts
            ],
            "weeks": [
                balance.CandidateWeek(recipe_ids=[fresh_a, fresh_b], total=10.0),
                balance.CandidateWeek(recipe_ids=[fresh_a, relaxed], total=9.0),
            ],
        }
    )

    result = pipeline.finalise(
        prepared,
        CorpusMealPlanResponse(
            week_summary="Two dinners.",
            chosen_week=0,
            suggestions=[
                CorpusMealPlanRecipe(external_id=external_id, title=prepared.titles[external_id], reason="Fine.")
                for external_id in (fresh_a, fresh_b)
            ],
        ),
    )
    alternatives = [suggestion.alternative for suggestion in result.suggestions]

    assert all(alternative is not None for alternative in alternatives)
    assert relaxed not in {alternative.external_id for alternative in alternatives if alternative}


def test_prepare_feeds_the_urgent_items_into_the_scorer(tmp_path: Path) -> None:
    # The unused-urgent row is only as good as its input: V4's urgent uses, by item name, per offered recipe.
    prepared = _prepared(
        tmp_path,
        pantry=[
            {"id": 1, "name": "coriander", "quantity": 50, "unit": "g", "urgency_score": 150.0, "expires_in_days": 2},
            # Four days out: V4's three-day rule does not make it urgent, so the scorer hears nothing about it.
            {"id": 2, "name": "haddock", "quantity": 200, "unit": "g", "urgency_score": 90.0, "expires_in_days": 4},
        ],
    )
    facts = {fact.recipe_id: fact for fact in prepared.facts}

    assert facts["rec_coriander_chicken"].urgent_items == ("coriander",)
    assert all("haddock" not in fact.urgent_items for fact in prepared.facts)
    assert prepared.weeks[0].recipe_ids  # the week still balances around the urgent item
    assert balance.unused_urgent_items(prepared.weeks[0]) == ()


def test_a_week_that_can_use_the_only_urgent_recipe_takes_it(tmp_path: Path) -> None:
    # Owner decision 2026-10-25: the row is what makes the generator take the salmon recipe even when its fit
    # is the weaker of two, because leaving the salmon to go off costs the week more than the fit it gains.
    prepared = _prepared(
        tmp_path,
        meals_per_week=2,
        pantry=[
            {"id": 1, "name": "haddock", "quantity": 200, "unit": "g", "urgency_score": 80.0, "expires_in_days": 2}
        ],
        exclude_external_ids=[
            "rec_coriander_chicken",
            "rec_tofu_noodles",
            "rec_chickpea_curry",
            "rec_slow_roast",
        ],
    )
    fishy = {fact.recipe_id: fact for fact in prepared.facts}["rec_fish_pie"]
    assert fishy.urgent_items == ("haddock",)
    assert "rec_fish_pie" in prepared.offered_ids

    assert "rec_fish_pie" in prepared.weeks[0].recipe_ids
    assert balance.unused_urgent_items(prepared.weeks[0]) == ()


def test_an_urgent_item_a_planned_meal_uses_is_not_charged_to_the_week(tmp_path: Path) -> None:
    # The reviewer's case: the lentil bake is already in the week and uses the potato, and the offered fish pie
    # uses it too. The week is not leaving the potato unused, so nothing may be charged for fish pie staying out.
    prepared = _prepared(
        tmp_path,
        meals_per_week=2,
        exclude_external_ids=["rec_lentil_bake"],
        pantry=[{"id": 1, "name": "potato", "quantity": 400, "unit": "g", "urgency_score": 90.0, "expires_in_days": 2}],
    )

    assert prepared.urgent_items_already_used == ["potato"]
    assert {fact.recipe_id: fact.urgent_items for fact in prepared.facts}["rec_fish_pie"] == ("potato",)
    assert all(balance.unused_urgent_items(week) == () for week in prepared.weeks)

    # A plan that leaves the second potato recipe out is charged nothing for it.
    context = balance.scoring_context(prepared.facts, urgent_items_already_used=prepared.urgent_items_already_used)
    elsewhere = next(external_id for external_id in prepared.offered_ids if external_id != "rec_fish_pie")
    assert score_meal_plan([elsewhere], context).points(Term.UNUSED_URGENT_ITEM) == 0.0


def test_prepare_does_not_force_a_second_recipe_for_a_planned_urgent_item(tmp_path: Path) -> None:
    # Through prepare, not just the scorer: the lentil bake already in the week uses the potato, and the offered
    # fish pie uses it too but is the weaker week. Before the fix the -4 charge for "leaving the potato unused"
    # put the fish pie in the week the model was shown; the strong recipe must win instead.
    prepared = _prepared(
        tmp_path,
        meals_per_week=1,
        exclude_external_ids=["rec_lentil_bake"],
        pantry=[
            {"id": 1, "name": "potato", "quantity": 400, "unit": "g", "urgency_score": 90.0, "expires_in_days": 2},
            {"id": 2, "name": "beef shin", "quantity": 500, "unit": "g", "urgency_score": 300.0},
        ],
    )

    assert prepared.urgent_items_already_used == ["potato"]
    assert prepared.weeks[0].recipe_ids == ["rec_slow_roast"]
    # Nothing is charged in either week: the pool's only urgent item is one a planned meal already uses.
    assert all(balance.unused_urgent_items(week) == () for week in prepared.weeks)
    assert all("unused_urgent_item" not in week.terms for week in prepared.weeks)
