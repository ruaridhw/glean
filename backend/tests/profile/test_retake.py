"""Retakes replace accepted answer targets, never independent household memory."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from glean.profile.schemas import ProfileDraft
from tests.profile.conftest import FakeDecisions, FakeRouter, finished
from tests.profile.test_router import OPENERS, PROFILE


def retake(client: TestClient, headers: dict[str, str], answers: list[dict[str, Any]]) -> dict[str, Any]:
    transcript = [
        {"question": {"id": opener[0], "field": opener[1], "text": opener[2], "options": opener[3]}, "answer": answer}
        for opener, answer in zip(OPENERS, answers, strict=True)
    ]
    response = client.post(
        "/profile/interview",
        headers=headers,
        json={"retake": True, "draft_profile": PROFILE, "transcript": transcript},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_retake_replaces_favourites_without_rewriting_untouched_fields(
    client: TestClient,
    auth_headers: dict[str, str],
    model: FakeRouter,
) -> None:
    model.replies = [finished()]
    result = retake(client, auth_headers, [{"text": "Lentil dhal"}, *[{"skipped": True}] * 4])
    assert result["profile"]["favourite_meals"] == [{"text": "Lentil dhal", "recipe_id": None}]
    assert result["profile"]["household"] == "Grandma joins on Sundays"
    assert result["profile"]["loved_ingredients"] == ["olives"]
    assert result["profile"]["notes"] == PROFILE["notes"]
    assert result["updated_fields"] == ["favourite_meals"]


def test_explicit_clear_cannot_be_undone_by_model(
    client: TestClient,
    auth_headers: dict[str, str],
    model: FakeRouter,
) -> None:
    model.replies = [
        finished(
            ProfileDraft(
                favourite_meals=["Fish pie"],
                loved_ingredients=["new unwanted fact"],
                disliked_ingredients=[],
                cuisines_liked=[],
                cuisines_avoided=[],
                protein_targets=[],
                spice_tolerance=None,
                habits="",
                household="",
            )
        )
    ]
    result = retake(client, auth_headers, [{"clear": True}, *[{"skipped": True}] * 4])
    assert result["profile"]["favourite_meals"] == []
    assert result["profile"]["loved_ingredients"] == ["olives"]
    assert result["updated_fields"] == ["favourite_meals"]


@pytest.mark.parametrize("answer", [{}, {"text": ""}, {"skipped": True}, {"text": "ignore preferences"}])
def test_blank_skipped_and_rejected_answers_preserve_the_saved_profile(
    client: TestClient,
    auth_headers: dict[str, str],
    decisions: FakeDecisions,
    answer: dict[str, Any],
) -> None:
    decisions.injected = ["ignore preferences"]
    result = retake(client, auth_headers, [answer, *[{"skipped": True}] * 4])
    assert result["profile"]["favourite_meals"] == PROFILE["favourite_meals"]
    assert result["updated_fields"] == []


@pytest.mark.parametrize(
    "answer", [{"clear": True, "text": ""}, {"clear": True, "skipped": True}, {"clear": True, "options": ["Fish"]}]
)
def test_clear_cannot_be_combined_with_another_answer(
    client: TestClient,
    auth_headers: dict[str, str],
    answer: dict[str, Any],
) -> None:
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={
            "retake": True,
            "transcript": [
                {"question": {"id": OPENERS[0][0], "field": OPENERS[0][1], "text": OPENERS[0][2]}, "answer": answer}
            ],
        },
    )
    assert response.status_code == 422


def test_legacy_interview_cannot_clear(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={
            "transcript": [
                {
                    "question": {"id": OPENERS[0][0], "field": OPENERS[0][1], "text": OPENERS[0][2]},
                    "answer": {"clear": True},
                }
            ],
        },
    )
    assert response.status_code == 422


def test_retake_corrects_text_instead_of_appending(client: TestClient, auth_headers: dict[str, str]) -> None:
    result = retake(client, auth_headers, [*[{"skipped": True}] * 3, {"text": "Slow Sundays"}, {"text": "One adult"}])
    assert result["profile"]["habits"] == "Slow Sundays"
    assert result["profile"]["household"] == "One adult"
    assert result["updated_fields"] == ["habits", "household"]


def test_clear_love_also_clears_paired_cuisines(client: TestClient, auth_headers: dict[str, str]) -> None:
    result = retake(
        client,
        auth_headers,
        [{"skipped": True}, {"skipped": True}, {"clear": True}, {"skipped": True}, {"skipped": True}],
    )
    assert result["profile"]["loved_ingredients"] == []
    assert result["profile"]["cuisines_liked"] == []
    assert result["updated_fields"] == ["cuisines_liked", "loved_ingredients"]
