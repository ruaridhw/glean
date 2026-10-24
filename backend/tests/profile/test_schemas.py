"""The interview's wire contract: the exact JSON both clients build against."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from glean.profile.schemas import (
    MAX_TURNS,
    FollowUp,
    HouseholdProfile,
    InterviewAnswer,
    InterviewQuestion,
    InterviewRequest,
    MainProtein,
    ProfileField,
    ProteinTarget,
    SpiceTolerance,
)

PROFILE_JSON = {
    "version": 1,
    "favourite_meals": [{"text": "Fish pie", "recipe_id": "corpus:fish-pie"}, {"text": "Pad thai", "recipe_id": None}],
    "loved_ingredients": ["olives"],
    "disliked_ingredients": ["anchovies"],
    "cuisines_liked": ["Spanish"],
    "cuisines_avoided": ["Thai"],
    "protein_targets": [{"protein": "fish", "min_per_week": 2, "max_per_week": 3}],
    "spice_tolerance": "medium",
    "habits": "Batch cook on Sundays",
    "household": "Four of us",
    "notes": [{"date": "2026-10-19", "text": "prefers rice midweek", "source": "interview"}],
    "interviewed_at": "2026-10-19T18:00:00Z",
}


def test_the_profile_shape_is_exactly_the_contract() -> None:
    profile = HouseholdProfile.model_validate(PROFILE_JSON)

    dumped = profile.model_dump(mode="json")

    assert dumped == {**PROFILE_JSON, "interviewed_at": "2026-10-19T18:00:00Z"}
    assert list(dumped) == [
        "version",
        "favourite_meals",
        "loved_ingredients",
        "disliked_ingredients",
        "cuisines_liked",
        "cuisines_avoided",
        "protein_targets",
        "spice_tolerance",
        "habits",
        "household",
        "notes",
        "interviewed_at",
    ]


def test_an_empty_profile_is_version_one_with_nothing_known() -> None:
    assert HouseholdProfile().model_dump(mode="json") == {
        "version": 1,
        "favourite_meals": [],
        "loved_ingredients": [],
        "disliked_ingredients": [],
        "cuisines_liked": [],
        "cuisines_avoided": [],
        "protein_targets": [],
        "spice_tolerance": None,
        "habits": "",
        "household": "",
        "notes": [],
        "interviewed_at": None,
    }


def test_the_profile_rejects_an_unknown_field_or_version() -> None:
    with pytest.raises(ValidationError):
        HouseholdProfile.model_validate({**PROFILE_JSON, "secret": "x"})
    with pytest.raises(ValidationError):
        HouseholdProfile.model_validate({**PROFILE_JSON, "version": 2})


def test_a_question_is_always_skippable() -> None:
    question = InterviewQuestion(
        id="opener-weeks", text="How do your weeks usually go?", options=["Quick weeknights"], field="habits"
    )

    assert question.model_dump(mode="json") == {
        "id": "opener-weeks",
        "text": "How do your weeks usually go?",
        "options": ["Quick weeknights"],
        "field": "habits",
        "skippable": True,
    }
    with pytest.raises(ValidationError):
        InterviewQuestion(id="x", text="q", field="habits", skippable=False)


def test_a_question_field_must_be_a_profile_field() -> None:
    with pytest.raises(ValidationError):
        InterviewQuestion(id="x", text="q", field="password")


def test_the_request_round_trips_what_the_app_sends() -> None:
    request = InterviewRequest.model_validate(
        {
            "transcript": [
                {
                    "question": {
                        "id": "opener-weeks",
                        "text": "How do your weeks usually go?",
                        "options": ["Quick weeknights"],
                        "field": "habits",
                        "skippable": True,
                    },
                    "answer": {"text": "Quick weeknights", "options": ["Quick weeknights"], "skipped": False},
                }
            ],
            "draft_profile": PROFILE_JSON,
        }
    )

    assert request.transcript[0].answer.text == "Quick weeknights"
    assert request.draft_profile.spice_tolerance is SpiceTolerance.MEDIUM


def test_the_request_defaults_to_an_empty_interview() -> None:
    request = InterviewRequest()

    assert request.transcript == []
    assert request.draft_profile == HouseholdProfile()


def test_the_transcript_is_capped_at_the_maximum_turn_count() -> None:
    turn = {
        "question": {"id": "q", "text": "q?", "options": [], "field": "habits", "skippable": True},
        "answer": {"text": None, "options": [], "skipped": True},
    }

    assert len(InterviewRequest.model_validate({"transcript": [turn] * MAX_TURNS}).transcript) == MAX_TURNS
    with pytest.raises(ValidationError):
        InterviewRequest.model_validate({"transcript": [turn] * (MAX_TURNS + 1)})


def test_the_answer_rejects_unknown_fields() -> None:
    assert InterviewAnswer().model_dump() == {"text": None, "options": [], "skipped": False}
    with pytest.raises(ValidationError):
        InterviewAnswer.model_validate({"text": "fish pies", "dropped": True})


def test_a_protein_target_needs_ordered_bounds() -> None:
    assert ProteinTarget(protein="fish", min_per_week=2).protein is MainProtein.FISH
    with pytest.raises(ValidationError):
        ProteinTarget(protein="fish", min_per_week=3, max_per_week=1)
    with pytest.raises(ValidationError):
        ProteinTarget(protein="sausages", min_per_week=1)


def test_the_main_protein_values_are_the_settled_ones() -> None:
    assert [protein.value for protein in MainProtein] == [
        "chicken",
        "turkey_or_duck",
        "beef",
        "pork",
        "lamb",
        "fish",
        "seafood",
        "beans_and_pulses",
        "tofu_or_plant_protein",
        "vegetarian_other",
        "mixed",
        "none",
    ]


def test_the_spice_values_are_the_settled_ones() -> None:
    assert [spice.value for spice in SpiceTolerance] == ["none", "mild", "medium", "hot"]


def test_a_follow_up_targets_a_profile_field() -> None:
    follow_up = FollowUp(text="How spicy is too spicy?", field=ProfileField.SPICE_TOLERANCE, options=["Mild"])

    assert follow_up.model_dump(mode="json") == {
        "text": "How spicy is too spicy?",
        "field": "spice_tolerance",
        "options": ["Mild"],
    }
