"""Every interview-owned preference remains addressable after manual editing is removed."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.profile.test_router import OPENERS, PROFILE


def five_skips() -> list[dict[str, Any]]:
    return [{"question": {"id": q[0], "field": q[1], "text": q[2]}, "answer": {"skipped": True}} for q in OPENERS]


def test_retake_always_asks_spice_and_protein_even_when_not_previously_set(
    client: TestClient, auth_headers: dict[str, str],
) -> None:
    transcript = five_skips()
    for field in ["spice_tolerance", "protein_targets"]:
        response = client.post("/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "question"
        assert body["question"]["field"] == field
        assert body["max_turns"] == 7
        transcript.append({"question": body["question"], "answer": {"skipped": True}})
    response = client.post("/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript})
    assert response.json()["status"] == "done"


def test_a_retake_cannot_retarget_the_fixed_spice_question_to_another_field(
    client: TestClient, auth_headers: dict[str, str],
) -> None:
    transcript = five_skips() + [{"question": {"id": "follow-up-6", "field": "household", "text": "q"},
                                 "answer": {"clear": True}}]
    response = client.post("/profile/interview", headers=auth_headers, json={"retake": True, "transcript": transcript})
    assert response.status_code == 422


@pytest.mark.parametrize('field', ['spice_tolerance', 'protein_targets'])
def test_uninterpreted_typed_answer_does_not_implicitly_clear_the_saved_target(
    client: TestClient, auth_headers: dict[str, str], field: str,
) -> None:
    transcript = five_skips() + [
        {"question": {"id": "follow-up-6", "field": "spice_tolerance", "text": "How spicy?"}, "answer": {"text": "Not sure"} if field == 'spice_tolerance' else {"skipped": True}},
        {"question": {"id": "follow-up-7", "field": "protein_targets", "text": "How often?"},
         "answer": {"text": "Fish whenever"} if field == 'protein_targets' else {"skipped": True}},
    ]
    response = client.post("/profile/interview", headers=auth_headers,
                           json={"retake": True, "transcript": transcript, "draft_profile": PROFILE})
    assert response.status_code == 200
    body = response.json()
    assert body["profile"][field] == PROFILE[field]
    assert field not in body["updated_fields"]
    assert body["unapplied_fields"] == [field]
