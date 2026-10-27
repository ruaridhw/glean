"""The household profile as a meal-plan request carries it (V13b): bounded, and refused rather than clipped."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from glean.meal_plan.profile_notes import MAX_PROFILE_NOTE_CHARS
from glean.meal_plan.schemas import (
    MAX_PLANNING_DISMISSED_NOTES,
    MAX_PLANNING_LIST_ENTRIES,
    MAX_PLANNING_NOTE_CHARS,
    MAX_PLANNING_NOTES,
    MAX_PLANNING_PARAGRAPH_CHARS,
    MAX_PLANNING_TEXT_CHARS,
    MealPlanRequest,
    PlanningProfile,
)


def _request(**overrides: Any) -> dict[str, Any]:
    return {
        "source": "corpus",
        "pantry": [],
        "purchase_tolerance": 0.3,
        "meals_per_week": 3,
        "dietary_flags": [],
        "max_active_time_mins": None,
        **overrides,
    }


def _profile(**overrides: Any) -> dict[str, Any]:
    return {
        "version": 1,
        "favourite_meals": [{"text": "Fish pie", "recipe_id": "rec_pie"}],
        "loved_ingredients": ["basil"],
        "disliked_ingredients": ["mushrooms"],
        "cuisines_liked": ["Italian"],
        "cuisines_avoided": ["Thai"],
        "protein_targets": [{"protein": "fish", "min_per_week": 1, "max_per_week": None}],
        "spice_tolerance": "mild",
        "habits": "Quick weeknights",
        "household": "Two adults, one child",
        "notes": [{"date": "2026-10-20", "text": "Prefers rice midweek", "source": "feedback"}],
        "interviewed_at": "2026-10-19T09:00:00Z",
        **overrides,
    }


def test_a_request_without_a_profile_plans_without_one() -> None:
    assert MealPlanRequest.model_validate(_request()).profile is None
    assert MealPlanRequest.model_validate(_request(profile=None)).profile is None


def test_the_profile_the_app_stores_is_accepted_as_sent() -> None:
    profile = MealPlanRequest.model_validate(_request(profile=_profile())).profile

    assert profile is not None
    assert profile.disliked_ingredients == ["mushrooms"]
    assert profile.favourite_meals[0].recipe_id == "rec_pie"
    assert profile.protein_targets[0].min_per_week == 1
    assert profile.notes[0].text == "Prefers rice midweek"


@pytest.mark.parametrize("field", ["loved_ingredients", "disliked_ingredients", "cuisines_liked", "cuisines_avoided"])
def test_a_list_longer_than_the_bound_is_refused(field: str) -> None:
    PlanningProfile.model_validate(_profile(**{field: [f"x{n}" for n in range(MAX_PLANNING_LIST_ENTRIES)]}))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(**{field: [f"x{n}" for n in range(MAX_PLANNING_LIST_ENTRIES + 1)]}))


def test_too_many_favourite_meals_are_refused() -> None:
    meals = [{"text": f"Meal {n}"} for n in range(MAX_PLANNING_LIST_ENTRIES + 1)]
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(favourite_meals=meals))


@pytest.mark.parametrize("field", ["loved_ingredients", "disliked_ingredients", "cuisines_liked", "cuisines_avoided"])
def test_a_list_entry_longer_than_the_bound_is_refused_in_code_points(field: str) -> None:
    # Code points, the unit the app clips by: an emoji is one, however many UTF-16 units it takes.
    PlanningProfile.model_validate(_profile(**{field: ["🍄" * MAX_PLANNING_TEXT_CHARS]}))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(**{field: ["🍄" * (MAX_PLANNING_TEXT_CHARS + 1)]}))


def test_a_favourite_meal_may_be_as_long_as_a_corpus_title_but_no_longer() -> None:
    # 120 code points, the interview's own bound: an unmatched favourite matches by exact title, and a third of the
    # corpus's titles are longer than the 60 the other lists allow.
    PlanningProfile.model_validate(_profile(favourite_meals=[{"text": "🍲" * 120}]))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(favourite_meals=[{"text": "x" * 121}]))


@pytest.mark.parametrize("field", ["habits", "household"])
def test_free_text_longer_than_the_bound_is_refused(field: str) -> None:
    PlanningProfile.model_validate(_profile(**{field: "x" * MAX_PLANNING_PARAGRAPH_CHARS}))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(**{field: "x" * (MAX_PLANNING_PARAGRAPH_CHARS + 1)}))


def test_more_notes_than_the_newest_twenty_are_refused() -> None:
    note = {"date": "2026-10-20", "text": "A note", "source": "interview"}
    PlanningProfile.model_validate(_profile(notes=[note] * MAX_PLANNING_NOTES))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(notes=[note] * (MAX_PLANNING_NOTES + 1)))


def test_a_note_longer_than_the_bound_is_refused() -> None:
    long_note = {"date": "2026-10-20", "text": "x" * (MAX_PLANNING_NOTE_CHARS + 1), "source": "interview"}
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(notes=[long_note]))


def test_the_app_clips_to_the_same_numbers_the_server_refuses_past() -> None:
    # The app's clip (household_profile_request.dart) states these numbers too; a drift is a 422 on every Generate.
    PlanningProfile.model_validate(_profile(disliked_ingredients=["x" * 60] * 20, habits="x" * 500))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(disliked_ingredients=["x" * 61]))
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(
            _profile(notes=[{"date": "2026-10-20", "text": "x" * 201, "source": "feedback"}])
        )


def test_the_dismissed_notes_are_read_and_bounded() -> None:
    assert PlanningProfile.model_validate(_profile()).dismissed_notes == []
    newest = [f"Dismissed {index}" for index in range(MAX_PLANNING_DISMISSED_NOTES)]
    assert PlanningProfile.model_validate(_profile(dismissed_notes=newest)).dismissed_notes == newest
    assert PlanningProfile.model_validate(_profile(dismissed_notes=["x" * MAX_PROFILE_NOTE_CHARS])).dismissed_notes


@pytest.mark.parametrize(
    "dismissed",
    [["A note"] * (MAX_PLANNING_DISMISSED_NOTES + 1), ["x" * (MAX_PROFILE_NOTE_CHARS + 1)], [""]],
    ids=["too many", "too long", "empty"],
)
def test_dismissed_notes_past_the_bounds_are_refused(dismissed: list[str]) -> None:
    with pytest.raises(ValidationError):
        PlanningProfile.model_validate(_profile(dismissed_notes=dismissed))
