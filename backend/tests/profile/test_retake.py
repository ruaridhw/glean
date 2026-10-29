"""Retakes replace accepted answer targets, never independent household memory."""

from typing import Any

from fastapi.testclient import TestClient

from tests.profile.conftest import FakeRouter, finished
from tests.profile.test_router import OPENERS, PROFILE


def retake(client: TestClient, headers: dict[str, str], answers: list[dict[str, Any]]) -> dict[str, Any]:
    transcript = [
        {"question": {"id": opener[0], "field": opener[1], "text": opener[2], "options": opener[3]}, "answer": answer}
        for opener, answer in zip(OPENERS, answers, strict=True)
    ]
    response = client.post(
        "/profile/interview", headers=headers,
        json={"retake": True, "draft_profile": PROFILE, "transcript": transcript},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_retake_replaces_favourites_without_rewriting_untouched_fields(
    client: TestClient, auth_headers: dict[str, str], model: FakeRouter,
) -> None:
    model.replies = [finished()]
    result = retake(client, auth_headers, [{"text": "Lentil dhal"}, *[{"skipped": True}] * 4])
    assert result["profile"]["favourite_meals"] == [{"text": "Lentil dhal", "recipe_id": None}]
    assert result["profile"]["household"] == "Grandma joins on Sundays"
    assert result["profile"]["loved_ingredients"] == ["olives"]
    assert result["profile"]["notes"] == PROFILE["notes"]
    assert result["updated_fields"] == ["favourite_meals"]
