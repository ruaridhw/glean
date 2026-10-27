"""V15: which of the agent's profile notes reach the household (spec §6.4 "Feedback into the profile").

Seam: `profile_notes.kept_notes`, the pure rule the graph's `finalise` applies to a `propose` action's notes. It
catches a note over the limits, an empty or repeated one, and one whose evidence this session never had. It
misses whether the graph hands it the right evidence, which `tests/agent/test_profile_notes.py` pins.
"""

from __future__ import annotations

from typing import Any

import pytest

from glean.meal_plan.profile_notes import (
    MAX_PROFILE_NOTE_CHARS,
    MAX_PROFILE_NOTES,
    SessionEvidence,
    kept_notes,
    known_notes,
    note_digest,
)
from glean.meal_plan.schemas import MealPlanRequest, NoteEvidence, ProfileNote

EVERYTHING = SessionEvidence(rated=True, answered=True, swap_note=True)


def note(text: str, evidence: NoteEvidence = NoteEvidence.RATING) -> ProfileNote:
    return ProfileNote(text=text, evidence=evidence)


def test_a_note_with_its_evidence_is_kept_trimmed() -> None:
    kept, dropped = kept_notes([note("  You prefer rice over pasta midweek.  ")], EVERYTHING)

    assert kept == [note("You prefer rice over pasta midweek.")]
    assert dropped == {}


def test_at_most_three_notes_are_kept() -> None:
    notes = [note(f"Note number {index}") for index in range(5)]

    kept, dropped = kept_notes(notes, EVERYTHING)

    assert [n.text for n in kept] == ["Note number 0", "Note number 1", "Note number 2"]
    assert len(kept) == MAX_PROFILE_NOTES
    assert dropped == {"over_limit": 2}


def test_the_length_limit_counts_code_points_after_trimming() -> None:
    # Emoji are one code point each and more than one UTF-16 unit; the limit is the code points.
    at_limit = "🍚" * MAX_PROFILE_NOTE_CHARS
    over = "a" * (MAX_PROFILE_NOTE_CHARS + 1)

    kept, dropped = kept_notes([note(f"   {at_limit}   "), note(over, NoteEvidence.ANSWER)], EVERYTHING)

    assert [n.text for n in kept] == [at_limit]
    assert dropped == {"too_long": 1}


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_an_empty_note_is_dropped(text: str) -> None:
    kept, dropped = kept_notes([note(text)], EVERYTHING)

    assert kept == []
    assert dropped == {"empty": 1}


def test_a_repeat_is_dropped_whatever_its_case_or_spacing() -> None:
    kept, dropped = kept_notes(
        [note("Likes fish on Fridays"), note("likes FISH on fridays ", NoteEvidence.ANSWER)], EVERYTHING
    )

    assert [n.text for n in kept] == ["Likes fish on Fridays"]
    assert dropped == {"duplicate": 1}


def test_a_dropped_note_does_not_use_up_one_of_the_three() -> None:
    notes = [note(""), note("One"), note("one"), note("Two"), note("Three")]

    kept, _ = kept_notes(notes, EVERYTHING)

    assert [n.text for n in kept] == ["One", "Two", "Three"]


@pytest.mark.parametrize(
    ("evidence", "session"),
    [
        (NoteEvidence.RATING, SessionEvidence(rated=False, answered=True, swap_note=True)),
        (NoteEvidence.ANSWER, SessionEvidence(rated=True, answered=False, swap_note=True)),
        (NoteEvidence.SWAP_NOTE, SessionEvidence(rated=True, answered=True, swap_note=False)),
    ],
)
def test_a_note_whose_evidence_the_session_lacks_is_dropped(evidence: NoteEvidence, session: SessionEvidence) -> None:
    kept, dropped = kept_notes([note("Prefers rice over pasta", evidence)], session)

    assert kept == []
    assert dropped == {"no_evidence": 1}


@pytest.mark.parametrize("evidence", list(NoteEvidence))
def test_each_kind_of_evidence_is_enough_on_its_own(evidence: NoteEvidence) -> None:
    session = SessionEvidence(
        rated=evidence is NoteEvidence.RATING,
        answered=evidence is NoteEvidence.ANSWER,
        swap_note=evidence is NoteEvidence.SWAP_NOTE,
    )

    kept, _ = kept_notes([note("Prefers rice over pasta", evidence)], session)

    assert [n.evidence for n in kept] == [evidence]


def test_no_evidence_at_all_keeps_nothing() -> None:
    nothing = SessionEvidence(rated=False, answered=False, swap_note=False)

    kept, dropped = kept_notes([note("A", e) for e in NoteEvidence], nothing)

    assert kept == []
    assert dropped == {"no_evidence": 3}


def test_a_note_the_profile_already_holds_or_the_household_dismissed_is_dropped() -> None:
    notes = [note("You prefer rice over pasta."), note("Likes fish"), note("The kids avoid chilli")]

    known = [note_digest("you prefer RICE over pasta."), note_digest("  the kids avoid  chilli")]

    kept, dropped = kept_notes(notes, EVERYTHING, known=known)

    assert [n.text for n in kept] == ["Likes fish"]
    assert dropped == {"known": 2}


def _request(profile: dict[str, Any] | None) -> MealPlanRequest:
    return MealPlanRequest.model_validate(
        {
            "source": "corpus",
            "pantry": [],
            "purchase_tolerance": 0.5,
            "meals_per_week": 2,
            "dietary_flags": [],
            "max_active_time_mins": None,
            "profile": profile,
        }
    )


def test_the_known_notes_are_the_profiles_notes_and_its_dismissed_ones() -> None:
    request = _request(
        {
            "notes": [{"date": "2026-10-20", "text": "Likes rice", "source": "feedback"}],
            "dismissed_notes": ["Likes chilli"],
        }
    )

    assert known_notes(request) == ["Likes rice", "Likes chilli"]
    assert known_notes(_request(None)) == []


def test_a_note_is_compared_with_a_known_one_by_digest_whatever_its_case_or_spacing() -> None:
    assert note_digest(" You prefer RICE  over pasta. ") == note_digest("you prefer rice over pasta.")
    assert note_digest("Likes rice") != note_digest("Likes fish")
    assert "rice" not in note_digest("Likes rice")


def test_a_kept_note_is_one_line_with_single_spaces() -> None:
    kept, _ = kept_notes([note("  You prefer\n rice   over\tpasta.  ")], EVERYTHING)

    assert [n.text for n in kept] == ["You prefer rice over pasta."]


@pytest.mark.parametrize(
    "text",
    [
        "Likes fish\x00 on Fridays",  # Cc: a control character
        "Likes fish\x1b[31m on Fridays",  # Cc: an escape sequence
        "Likes\u200b fish",  # Cf: a zero-width space
        "Likes fish\u202e syadirF",  # Cf: a right-to-left override
        "Likes fish\ufeff",  # Cf: a byte-order mark
        "Likes fish\ue000",  # Co: a private-use character
        "Likes fish\U000f0000",  # Co: a supplementary private-use character
        "Likes fish\u0378",  # Cn: an unassigned code point
    ],
)
def test_a_note_with_a_control_format_private_or_unassigned_character_is_dropped_as_invalid(text: str) -> None:
    kept, dropped = kept_notes([note(text), note("Likes rice")], EVERYTHING)

    assert [n.text for n in kept] == ["Likes rice"]
    assert dropped == {"invalid": 1}
