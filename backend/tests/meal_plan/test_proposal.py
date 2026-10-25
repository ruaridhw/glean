"""The proposal `finalise` writes: week summary, reason kinds, alternatives and the degraded fallback.

The pipeline is exercised for real -- the sampler, the dietary and recency filters, and the reason
writer. Only the model's answer is a value this file writes by hand, because the point is what
`finalise` does with a model's answer, not what a model would say.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from glean.meal_plan import pipeline
from glean.meal_plan.schemas import (
    CorpusMealPlanAlternative,
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    CorpusPlannedAlternative,
    MealPlanRequest,
    MealPlanSuggestion,
    ReasonKind,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.enrichment.active_time import active_time_question
from glean.recipes.enrichment.attributes import attribute_questions
from glean.recipes.enrichment.enricher import MIN_ATTRIBUTE_BAR
from glean.recipes.stored import StoredIngredient, StoredRecipe
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
        active_time="15-30",
    )

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    suggestion = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)])).suggestions[0]

    assert suggestion.attributes.model_dump() == {
        "main_protein": "chicken",
        "main_carb": "rice",
        "dish_type": "curry",
        "active_time_mins": 30,
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
    first = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    chosen, alternative = first.offered_ids[0], first.offered_ids[1]
    _enrich(corpus, alternative, main_protein="fish", active_time="<=15")

    prepared = pipeline.prepare(_request(), corpus=corpus, rng=random.Random(0), now=NOW)
    result = pipeline.finalise(prepared, _draft(prepared, suggestions=[_pick(prepared, 0)], planned=[]))
    swap = result.suggestions[0].alternative

    assert swap is not None
    assert swap.external_id == alternative
    assert (swap.attributes.main_protein, swap.attributes.active_time_mins) == ("fish", 15)
    assert chosen != alternative


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
    assert [suggestion.external_id for suggestion in result.suggestions] == prepared.offered_ids[:MEALS]
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
