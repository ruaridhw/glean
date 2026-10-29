"""Offered heat choices have deterministic meanings, independent of model extraction."""

import pytest
from fastapi.testclient import TestClient

from tests.profile.test_retake_reachability import five_skips
from tests.profile.test_router import PROFILE


@pytest.mark.parametrize(
    ("option", "expected"), [("Not at all", "none"), ("Mild", "mild"), ("Medium", "medium"), ("Hot", "hot")]
)
def test_offered_spice_choice_replaces_the_saved_value(
    client: TestClient,
    auth_headers: dict[str, str],
    option: str,
    expected: str,
) -> None:
    transcript = [
        *five_skips(),
        {
            "question": {"id": "follow-up-6", "field": "spice_tolerance", "text": "How spicy?"},
            "answer": {"options": [option]},
        },
        {
            "question": {"id": "follow-up-7", "field": "protein_targets", "text": "How often?"},
            "answer": {"skipped": True},
        },
    ]
    response = client.post(
        "/profile/interview",
        headers=auth_headers,
        json={"retake": True, "transcript": transcript, "draft_profile": PROFILE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["spice_tolerance"] == expected
    assert body["updated_fields"] == ["spice_tolerance"]
    assert body["unapplied_fields"] == []
