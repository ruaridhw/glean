"""Every interview-owned preference remains addressable after manual editing is removed."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from glean.profile.schemas import MainProtein, ProteinTarget
from tests.profile.conftest import FakeRouter, empty_draft, finished
from tests.profile.test_retake import retake
from tests.profile.test_router import OPENERS, PROFILE


def five_skips() -> list[dict[str, Any]]:
    return [{"question": {"id": q[0], "field": q[1], "text": q[2]}, "answer": {"skipped": True}} for q in OPENERS]


def test_retake_always_asks_spice_and_protein_even_when_not_previously_set(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    transcript = five_skips()
    for field in ["spice_tolerance", "protein_targets"]:
        response = client.post(
            "/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "question"
        assert body["question"]["field"] == field
        assert body["max_turns"] == 7
        transcript.append({"question": body["question"], "answer": {"skipped": True}})
    response = client.post("/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript})
    assert response.json()["status"] == "done"


@pytest.mark.parametrize("turn", [6, 7])
def test_a_retake_cannot_retarget_fixed_questions_to_another_field(
    client: TestClient,
    auth_headers: dict[str, str],
    turn: int,
) -> None:
    transcript = five_skips()
    if turn == 7:
        transcript.append(
            {
                "question": {"id": "follow-up-6", "field": "spice_tolerance", "text": "How spicy?"},
                "answer": {"skipped": True},
            }
        )
    transcript.append(
        {"question": {"id": f"follow-up-{turn}", "field": "household", "text": "q"}, "answer": {"clear": True}}
    )
    response = client.post("/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript})
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["spice_tolerance", "protein_targets"])
def test_uninterpreted_typed_answer_does_not_implicitly_clear_the_saved_target(
    client: TestClient,
    auth_headers: dict[str, str],
    field: str,
) -> None:
    transcript = [
        *five_skips(),
        {
            "question": {"id": "follow-up-6", "field": "spice_tolerance", "text": "How spicy?"},
            "answer": {"text": "Not sure"} if field == "spice_tolerance" else {"skipped": True},
        },
        {
            "question": {"id": "follow-up-7", "field": "protein_targets", "text": "How often?"},
            "answer": {"text": "Fish whenever"} if field == "protein_targets" else {"skipped": True},
        },
    ]
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={"retake": True, "transcript": transcript, "draft_profile": PROFILE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"][field] == PROFILE[field]
    assert field not in body["updated_fields"]
    assert body["unapplied_fields"] == [field]


@pytest.mark.parametrize(
    ("opener", "fields"),
    [(1, ["cuisines_avoided", "disliked_ingredients"]), (2, ["cuisines_liked", "loved_ingredients"])],
)
def test_screened_prose_without_any_parsed_fact_cannot_clear_a_pair(
    client: TestClient,
    auth_headers: dict[str, str],
    opener: int,
    fields: list[str],
) -> None:
    answers: list[dict[str, Any]] = [{"skipped": True} for _ in range(5)]
    answers[opener] = {"text": "verylongingredient" * 20}
    body = retake(client, auth_headers, answers)
    assert body["updated_fields"] == []
    assert body["unapplied_fields"] == fields
    for field in fields:
        assert body["profile"][field] == PROFILE[field]


def test_parsed_cuisine_replaces_the_entire_love_pair(client: TestClient, auth_headers: dict[str, str]) -> None:
    body = retake(
        client,
        auth_headers,
        [{"skipped": True}, {"skipped": True}, {"text": "Thai"}, {"skipped": True}, {"skipped": True}],
    )
    assert body["profile"]["loved_ingredients"] == []
    assert body["profile"]["cuisines_liked"] == ["Thai"]
    assert body["updated_fields"] == ["cuisines_liked", "loved_ingredients"]


def test_explicit_clear_of_both_typed_answers_is_preserved(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    transcript = five_skips()
    for _ in range(2):
        response = client.post(
            "/profile/interview",
            headers=auth_headers,
            json={"retake": True, "transcript": transcript, "draft_profile": PROFILE},
        )
        transcript.append({"question": response.json()["question"], "answer": {"clear": True}})
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={"retake": True, "transcript": transcript, "draft_profile": PROFILE},
    )
    body = response.json()
    assert body["profile"]["spice_tolerance"] is None
    assert body["profile"]["protein_targets"] == []
    assert body["updated_fields"] == ["protein_targets", "spice_tolerance"]


def test_retake_can_replace_typed_preferences_with_new_interpreted_values(
    client: TestClient,
    auth_headers: dict[str, str],
    model: FakeRouter,
) -> None:
    model.replies = [
        finished(
            empty_draft().model_copy(
                update={
                    "protein_targets": [ProteinTarget(protein=MainProtein.CHICKEN, min_per_week=3)],
                }
            )
        )
    ]
    transcript = [
        *five_skips(),
        {
            "question": {"id": "follow-up-6", "field": "spice_tolerance", "text": "How spicy?"},
            "answer": {"text": "Mild"},
        },
        {
            "question": {"id": "follow-up-7", "field": "protein_targets", "text": "How often?"},
            "answer": {"text": "Chicken at least three times a week"},
        },
    ]
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={"retake": True, "transcript": transcript, "draft_profile": PROFILE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["spice_tolerance"] == "mild"
    assert body["profile"]["protein_targets"] == [{"protein": "chicken", "min_per_week": 3, "max_per_week": None}]
    assert body["updated_fields"] == ["protein_targets", "spice_tolerance"]
    assert body["unapplied_fields"] == []
