from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from glean.meal_plan.schemas import MAX_COOKED_NOTE_LENGTH, CookedHistoryItem


def test_a_cooked_at_without_an_offset_is_read_as_utc() -> None:
    # The app always sends a UTC instant; an older build's local wall clock is read as UTC rather than
    # being rejected, so a request never fails over a missing offset.
    item = CookedHistoryItem(recipe_id="rec_a", title="A stew", cooked_at="2026-10-05T18:30:00")

    assert item.cooked_at == datetime(2026, 10, 5, 18, 30, tzinfo=UTC)


def test_a_cooked_at_with_an_offset_keeps_its_instant() -> None:
    item = CookedHistoryItem(recipe_id="rec_a", title="A stew", cooked_at="2026-10-05T18:30:00-07:00")

    assert item.cooked_at == datetime(2026, 10, 6, 1, 30, tzinfo=UTC)


def test_a_naive_cooked_at_after_normalisation_is_never_naive() -> None:
    item = CookedHistoryItem(title="A stew", cooked_at=datetime(2026, 10, 5, 18, 30))

    assert item.cooked_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize("rating", ["up", "down"])
def test_a_rating_is_one_of_the_two_thumbs(rating: str) -> None:
    item = CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", rating=rating)

    assert item.rating == rating


def test_an_unrecognised_rating_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z", rating="meh")


def test_a_cook_without_a_rating_or_a_note_is_accepted() -> None:
    item = CookedHistoryItem(title="A stew", cooked_at="2026-10-05T18:30:00Z")

    assert item.rating is None
    assert item.note is None


def test_a_note_is_accepted_up_to_its_bound() -> None:
    item = CookedHistoryItem(
        title="A stew",
        cooked_at="2026-10-05T18:30:00Z",
        rating="down",
        note="x" * MAX_COOKED_NOTE_LENGTH,
    )

    assert item.note == "x" * MAX_COOKED_NOTE_LENGTH


def test_a_note_longer_than_its_bound_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CookedHistoryItem(
            title="A stew",
            cooked_at="2026-10-05T18:30:00Z",
            note="x" * (MAX_COOKED_NOTE_LENGTH + 1),
        )
